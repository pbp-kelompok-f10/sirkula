from copy import deepcopy
from email.message import Message as Headers
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from uuid import uuid4
import hashlib
import hmac
import json
import random

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.models import WardrobeItem, WardrobeItemImage
from apps.wardrobe.tests.test_private_photos import png_upload
from .api_client import WardrobeAPIClient, WardrobeAPIError, signed_headers
from .models import Conversation, Message, WardrobeAPIAccount, WardrobeAPIMapping, OutfitPreviewAttempt, OutfitUserPreviewBudget
from .preview_service import PREVIEW_LABEL
from .sync import canonical_photo, category_type


@override_settings(WARDROBE_API_URL="https://wardrobe.example", WARDROBE_SECRET="test-only-secret-" * 3, OUTFITS_API_TIMEOUT_SECONDS=1)
class APIClientTests(SimpleTestCase):
    def test_signature_matches_contract_and_binds_body_path_owner_and_method(self):
        body = b'{"mode":"best"}'
        message = "\n".join(["POST", "/v2/mix-match", "owner-1", "1700000000", "a" * 32, hashlib.sha256(body).hexdigest()])
        expected = hmac.new(b"contract-test-secret", message.encode(), hashlib.sha256).hexdigest()
        headers = signed_headers("contract-test-secret", "post", "/v2/mix-match", "owner-1", body, timestamp=1700000000, nonce="a" * 32)
        self.assertEqual(headers["X-Wardrobe-Signature"], expected)
        self.assertEqual(set(headers), {"X-Wardrobe-Owner", "X-Wardrobe-Time", "X-Wardrobe-Nonce", "X-Wardrobe-Signature"})
        for method, path, owner, value in (("GET", "/v2/mix-match", "owner-1", body), ("POST", "/v2/items", "owner-1", body), ("POST", "/v2/mix-match", "owner-2", body), ("POST", "/v2/mix-match", "owner-1", body+b" ")):
            other = signed_headers("contract-test-secret", method, path, owner, value, timestamp=1700000000, nonce="a" * 32)
            self.assertNotEqual(other["X-Wardrobe-Signature"], expected)

    def test_nonce_changes_on_every_request(self):
        self.assertNotEqual(signed_headers("secret", "GET", "/v2/items", "1")["X-Wardrobe-Nonce"], signed_headers("secret", "GET", "/v2/items", "1")["X-Wardrobe-Nonce"])

    def test_exact_sent_body_is_signed_and_secret_is_not_in_request(self):
        response = BytesIO(b'{"results":[]}')
        response.status = 200
        with patch("apps.outfits.api_client.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = response
            WardrobeAPIClient().match("owner", {"mode":"random", "seed":7})
            request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.data, b'{"mode":"random","seed":7}')
        self.assertNotIn("test-only-secret", str(request.header_items()))
        self.assertNotIn("test-only-secret", request.full_url)
        self.assertEqual(request.get_header("X-wardrobe-owner"), "owner")

    def test_errors_are_sanitized_without_exception_chaining_or_automatic_retry(self):
        for failure in (TimeoutError("secret-response"), URLError("secret-response"), HTTPError("https://wardrobe.example", 401, "secret-response", {}, None), HTTPError("https://wardrobe.example", 302, "secret-response", {}, None)):
            with self.subTest(failure=type(failure).__name__), patch("apps.outfits.api_client.build_opener") as opener:
                opener.return_value.open.side_effect = failure
                with self.assertRaises(WardrobeAPIError) as raised:
                    WardrobeAPIClient().request("owner", "GET", "/v2/health")
                self.assertNotIn("secret-response", str(raised.exception))
                self.assertTrue(raised.exception.__suppress_context__)
                self.assertEqual(opener.return_value.open.call_count, 1)

    def test_insecure_or_ambiguous_base_urls_and_missing_secret_are_rejected(self):
        for url in ("http://wardrobe.example", "https://user:password@wardrobe.example", "https://wardrobe.example/api", "https://wardrobe.example?token=1", ""):
            with self.subTest(url=url), override_settings(WARDROBE_API_URL=url):
                with self.assertRaises(WardrobeAPIError):
                    WardrobeAPIClient()
        with override_settings(WARDROBE_SECRET=""), self.assertRaises(WardrobeAPIError):
            WardrobeAPIClient()

    def test_oversized_and_non_json_responses_are_rejected(self):
        for raw in (b"x"*(1024*1024+1), b"not json", b"[]"):
            response = BytesIO(raw)
            response.status=200
            with patch("apps.outfits.api_client.build_opener") as opener:
                opener.return_value.open.return_value.__enter__.return_value=response
                with self.assertRaises(WardrobeAPIError):
                    WardrobeAPIClient().request("owner", "GET", "/v2/items")


class MemoryAPI:
    base_url = "https://wardrobe.example"
    def __init__(self):
        self.items = {}
        self.calls = []
        self.upload_lost = False
        self.upload_before_send = False
        self.malformed = None
        self.jobs = {}
        self.preview_calls = 0
        self.preview_lost = False

    def catalog(self, owner):
        self.calls.append(("catalog", owner))
        return {key:deepcopy(row) for key,row in self.items.get(owner,{}).items()}

    def put(self, owner, category, image, item_id=None):
        self.calls.append(("put" if item_id else "upload", owner))
        if self.upload_before_send:
            self.upload_before_send=False
            raise WardrobeAPIError(code="timeout")
        key = item_id or uuid4().hex
        self.items.setdefault(owner,{})[key] = {"item_id":key,"category":category,"revision":uuid4().hex,"status":"ready","image":canonical_photo(image)}
        if self.upload_lost:
            self.upload_lost=False
            raise WardrobeAPIError(code="timeout")
        return key

    def delete(self, owner, item_id):
        self.calls.append(("delete", owner))
        self.items.setdefault(owner,{}).pop(item_id,None)

    def item_image(self, owner, item_id):
        return self.items[owner][item_id]["image"]

    def match(self, owner, payload):
        self.calls.append(("match",owner,deepcopy(payload)))
        if self.malformed is not None:
            return deepcopy(self.malformed)
        rows=self.items.get(owner,{})
        if payload["mode"] == "manual":
            top,bottom=payload["baju_id"],payload["celana_id"]
        else:
            tops=[k for k,v in rows.items() if v["category"]=="baju"]
            bottoms=[k for k,v in rows.items() if v["category"]=="celana"]
            rng=random.Random(payload.get("seed"))
            top,bottom=rng.choice(tops),rng.choice(bottoms)
        pair={"baju_id":top,"celana_id":bottom,"score":0.75,"preview_status":"not_generated","preview_url":None}
        if (owner,top,bottom) in self.jobs:
            pair.update(self.jobs[(owner,top,bottom)])
        return {"results":[pair],"mode":payload["mode"],"model_version":"test-model"}

    def preview(self, owner, top, bottom):
        self.preview_calls+=1
        data={"preview_id":hashlib.sha256(f"{owner}:{top}:{bottom}".encode()).hexdigest(),"preview_status":"queued","baju_id":top,"celana_id":bottom,"preview_label":PREVIEW_LABEL}
        self.jobs[(owner,top,bottom)]=data
        if self.preview_lost:
            self.preview_lost=False
            raise WardrobeAPIError(code="timeout")
        return data

    def preview_status(self, owner, key):
        return next((deepcopy(job) for (who,_,_),job in self.jobs.items() if who==owner and job["preview_id"]==key),None)

    def preview_image(self, owner, key):
        return b"\x89PNG\r\n\x1a\nfixture"


@override_settings(OUTFITS_PROVIDER="api", WARDROBE_API_URL="https://wardrobe.example", WARDROBE_SECRET="test-only-secret-"*3,
                   OUTFITS_PREVIEW_ENABLED=False, OUTFITS_PREVIEW_MAX_REQUESTS=0)
class APIIntegrationTests(TestCase):
    def setUp(self):
        directory=TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        configuration=override_settings(WARDROBE_PRIVATE_ROOT=Path(directory.name))
        configuration.enable()
        self.addCleanup(configuration.disable)
        self.owner=get_user_model().objects.create_user(username="api-owner")
        self.other=get_user_model().objects.create_user(username="api-other")
        self.top=self.item(self.owner,"Kaos sungguhan","Kaos")
        self.bottom=self.item(self.owner,"Celana sungguhan","Celana")
        self.shoes=self.item(self.owner,"Sepatu rahasia","Sepatu")
        self.draft=self.item(self.owner,"Draft rahasia","Kaos",status="draft")
        self.foreign=self.item(self.other,"Akun lain rahasia","Kaos")
        self.remote=MemoryAPI()
        for location in ("apps.outfits.api_provider.WardrobeAPIClient","apps.outfits.preview_service.WardrobeAPIClient"):
            mock=patch(location,return_value=self.remote)
            mock.start()
            self.addCleanup(mock.stop)
        self.client.force_login(self.owner)
        self.index=reverse("outfits:index")

    def item(self, owner, name, category, status="active"):
        item=WardrobeItem.objects.create(owner=owner,name=name,status=status,category=owner.wardrobe_categories.get(name=category))
        WardrobeItemImage.objects.create(item=item,image=png_upload(),position=1)
        return item

    def start(self, prompt="best", key=None, **extra):
        key=key or uuid4()
        response=self.client.post(self.index,{"prompt":prompt,"request_key":key,**extra})
        return response,Conversation.objects.filter(owner=self.owner,creation_key=key).first()

    def url(self, conversation):
        return reverse("outfits:conversation",kwargs={"conversation_id":conversation.pk})

    def preview_url(self, conversation):
        return reverse("outfits:preview",kwargs={"conversation_id":conversation.pk})

    def test_best_syncs_only_owned_active_explicit_categories_and_writes_application_status(self):
        response,conversation=self.start()
        self.assertEqual(response.status_code,302)
        account=WardrobeAPIAccount.objects.get(owner=self.owner)
        self.assertNotEqual(account.api_owner,str(self.owner.pk))
        self.assertEqual(set(account.mappings.values_list("item_id",flat=True)),{self.top.pk,self.bottom.pk})
        self.assertEqual(len(self.remote.items[account.api_owner]),2)
        self.assertEqual(conversation.result["api"]["match_mode"],"best")
        self.assertEqual(list(conversation.messages.values_list("role",flat=True)),["user","status"])
        message=conversation.messages.last().content
        for name in (self.top.name,self.bottom.name): self.assertIn(name,message)
        for name in (self.shoes.name,self.draft.name,self.foreign.name): self.assertNotIn(name,message)
        self.assertEqual(self.remote.preview_calls,0)
        html=self.client.get(self.url(conversation))
        self.assertContains(html,"Status aplikasi")
        self.assertNotContains(html,"test-only-secret")
        self.assertNotIn("/v2/",html.content.decode())
        self.assertNotContains(html,"Akun lain rahasia")

    def test_category_map_is_an_explicit_allowlist(self):
        for name,expected in (("Kaos","baju"),("KEMEJA","baju"),("Outer","baju"),("Celana","celana"),("Sepatu",None),("Favorit",None),("Baju",None)):
            self.assertEqual(category_type({"category":{"name":name}}),expected)
        self.assertIsNone(category_type({"category":None}))

    def test_input_and_recommendation_cards_support_best_and_random(self):
        key=uuid4()
        response,conversation=self.start("acak",key=key)
        self.assertEqual(response.status_code,302)
        self.assertEqual(conversation.result["api"]["match_mode"],"random")
        calls=[call for call in self.remote.calls if call[0]=="match"]
        self.assertEqual(calls[-1][2],{"mode":"random","seed":key.int%2147483648})
        response=self.client.get(self.index)
        self.assertEqual([card["title"] for card in response.context["recommendations"]],["Best","Random","Best","Random"])
        self.assertNotContains(response,"landing-reference.png")
        response,card=self.start("forged",recommendation="demo-rec-2")
        self.assertEqual(response.status_code,302)
        self.assertEqual(card.messages.first().content,"random")
        self.assertEqual(card.result["api"]["match_mode"],"random")

    def test_user_catalog_namespaces_are_isolated(self):
        self.start()
        self.item(self.other,"Celana lain","Celana")
        self.client.force_login(self.other)
        response=self.client.post(self.index,{"prompt":"best","request_key":uuid4()})
        self.assertEqual(response.status_code,302)
        a=WardrobeAPIAccount.objects.get(owner=self.owner)
        b=WardrobeAPIAccount.objects.get(owner=self.other)
        self.assertNotEqual(a.namespace,b.namespace)
        self.assertEqual(len(self.remote.items[a.api_owner]),2)
        self.assertEqual(len(self.remote.items[b.api_owner]),2)

    def test_retry_saved_request_does_not_repeat_remote_requests_or_messages(self):
        key=uuid4()
        _,conversation=self.start(key=key)
        calls=len(self.remote.calls)
        response,_=self.start(key=key)
        self.assertEqual(response.status_code,302)
        self.assertEqual(len(self.remote.calls),calls)
        self.assertEqual(conversation.messages.count(),2)

    def test_lost_upload_response_is_reconciled_without_a_duplicate_post(self):
        self.remote.upload_lost=True
        key=uuid4()
        response,_=self.start(key=key)
        self.assertEqual(response.status_code,503)
        self.assertFalse(Conversation.objects.exists())
        self.assertTrue(WardrobeAPIMapping.objects.get().upload_pending)
        response,conversation=self.start(key=key)
        self.assertEqual(response.status_code,302)
        self.assertEqual(len([call for call in self.remote.calls if call[0]=="upload"]),2)
        self.assertEqual(conversation.messages.count(),2)
        self.assertFalse(WardrobeAPIMapping.objects.filter(upload_pending=True).exists())

    def test_uncertain_upload_without_remote_proof_is_blocked_instead_of_resent(self):
        self.remote.upload_before_send=True
        key=uuid4()
        self.assertEqual(self.start(key=key)[0].status_code,503)
        self.assertEqual(self.start(key=key)[0].status_code,409)
        self.assertEqual(len([call for call in self.remote.calls if call[0]=="upload"]),1)
        self.assertFalse(Conversation.objects.exists())

    def test_changed_photo_uses_put_and_removed_items_are_deleted_on_next_sync(self):
        self.start()
        mapping=WardrobeAPIMapping.objects.get(item=self.top)
        old_id=mapping.api_id
        photo=self.top.images.get()
        photo.delete()
        WardrobeItemImage.objects.create(item=self.top,image=png_upload(),position=1)
        self.start()
        mapping.refresh_from_db()
        self.assertEqual(mapping.api_id,old_id)
        self.assertEqual(len([call for call in self.remote.calls if call[0]=="put"]),1)
        self.bottom.delete()
        response,_=self.start()
        self.assertEqual(response.status_code,400)
        self.assertEqual(len(self.remote.items[mapping.account.api_owner]),1)

    def test_empty_active_wardrobe_cleans_remote_catalog_without_creating_chat(self):
        self.start()
        WardrobeItem.objects.filter(owner=self.owner,status="active").delete()
        response,_=self.start()
        self.assertEqual(response.status_code,400)
        account=WardrobeAPIAccount.objects.get(owner=self.owner)
        self.assertEqual(self.remote.items[account.api_owner],{})
        self.assertEqual(Conversation.objects.count(),1)

    def test_missing_opposite_category_does_not_invent_an_outfit(self):
        self.bottom.delete()
        response,conversation=self.start()
        self.assertEqual(response.status_code,400)
        self.assertIsNone(conversation)
        self.assertContains(response,"minimal satu Kaos/Kemeja/Outer dan satu Celana",status_code=400)
        self.assertEqual(self.remote.preview_calls,0)

    def test_foreign_ids_invalid_categories_and_bad_score_do_not_write_chat(self):
        for pair in ({"baju_id":"unknown","celana_id":"unknown","score":.5},{"baju_id":"wrong","celana_id":"wrong","score":float("nan")}):
            self.remote.malformed={"results":[pair],"mode":"best"}
            response,conversation=self.start()
            self.assertEqual(response.status_code,503)
            self.assertIsNone(conversation)
        self.assertFalse(Message.objects.exists())

    def test_match_failure_preserves_previous_history_and_retry_reuses_mappings(self):
        _,conversation=self.start()
        before=deepcopy(conversation.result)
        key=uuid4()
        with patch.object(self.remote,"match",side_effect=WardrobeAPIError(code="timeout")):
            response=self.client.post(self.url(conversation),{"prompt":"acak","request_key":key,"version":1},HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code,503)
        conversation.refresh_from_db()
        self.assertEqual(conversation.result,before)
        self.assertEqual(conversation.messages.count(),2)
        response=self.client.post(self.url(conversation),{"prompt":"acak","request_key":key,"version":1},HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code,200)
        self.assertEqual(conversation.messages.count(),4)
        self.assertEqual(len([call for call in self.remote.calls if call[0]=="upload"]),2)

    def test_busy_account_prevents_concurrent_sync(self):
        self.start()
        from datetime import timedelta
        from django.utils import timezone
        WardrobeAPIAccount.objects.filter(owner=self.owner).update(lease_token=uuid4(),lease_until=timezone.now()+timedelta(seconds=120))
        calls=len(self.remote.calls)
        response,_=self.start()
        self.assertEqual(response.status_code,409)
        self.assertEqual(len(self.remote.calls),calls)

    def test_generated_preview_requires_explicit_host_allowance(self):
        _,conversation=self.start()
        response=self.client.post(self.preview_url(conversation))
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.remote.preview_calls,0)
        self.assertFalse(OutfitPreviewAttempt.objects.exists())
        self.assertFalse(OutfitUserPreviewBudget.objects.exists())
        response=self.client.get(self.preview_url(conversation))
        self.assertEqual(response.json()["preview_status"],"disabled")
        self.assertEqual(self.remote.preview_calls,0)

    @override_settings(OUTFITS_PREVIEW_ENABLED=True,OUTFITS_PREVIEW_MAX_REQUESTS=1)
    def test_preview_enqueue_is_explicit_budgeted_and_not_repeated(self):
        _,conversation=self.start()
        url=self.preview_url(conversation)
        self.assertEqual(self.client.post(url).status_code,200)
        self.assertEqual(self.client.post(url).status_code,200)
        self.assertEqual(self.remote.preview_calls,1)
        self.assertEqual(OutfitUserPreviewBudget.objects.get().attempts,1)
        self.assertEqual(self.client.get(url).json()["preview_status"],"queued")
        self.assertEqual(self.remote.preview_calls,1)

    @override_settings(OUTFITS_PREVIEW_ENABLED=True,OUTFITS_PREVIEW_MAX_REQUESTS=1)
    def test_lost_preview_enqueue_response_only_checks_existing_job(self):
        self.remote.preview_lost=True
        response,conversation=self.start()
        self.assertEqual(response.status_code,302)
        url=self.preview_url(conversation)
        self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(self.client.post(url).status_code,200)
        self.assertEqual(self.remote.preview_calls,1)
        self.assertEqual(OutfitUserPreviewBudget.objects.get().attempts,1)

    @override_settings(OUTFITS_PREVIEW_ENABLED=True,OUTFITS_PREVIEW_MAX_REQUESTS=1)
    def test_ready_preview_is_proxied_privately_and_stale_pair_is_denied(self):
        _,conversation=self.start()
        self.client.post(self.preview_url(conversation))
        for job in self.remote.jobs.values(): job["preview_status"]="ready"
        status=self.client.get(self.preview_url(conversation))
        self.assertEqual(status.json()["preview_label"],PREVIEW_LABEL)
        self.assertNotIn("preview_id",status.json())
        image_url=status.json()["preview_url"]
        response=self.client.get(image_url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response["Content-Type"],"image/png")
        self.assertIn("private",response["Cache-Control"])
        self.assertIn("no-store",response["Cache-Control"])
        self.assertIn("Cookie",response["Vary"])
        self.top.name="Sudah berubah"
        self.top.save()
        self.assertEqual(self.client.get(image_url).status_code,404)

    def test_other_users_anonymous_and_csrf_cannot_access_previews(self):
        _,conversation=self.start()
        url=self.preview_url(conversation)
        image_url=reverse("outfits:preview_image",kwargs={"conversation_id":conversation.pk})
        secured=Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(url).status_code,403)
        for user in (self.other,None):
            if user: self.client.force_login(user)
            else: self.client.logout()
            for target in (url,image_url):
                self.assertEqual(self.client.get(target).status_code,404)
            self.assertEqual(self.client.post(url).status_code,404)
        self.assertEqual(self.remote.preview_calls,0)


    def test_preview_requests_bound_to_an_old_conversation_version_are_rejected(self):
        _, conversation = self.start()
        url = self.preview_url(conversation) + "?version=1"
        conversation.version = 2
        conversation.save(update_fields=["version"])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.remote.preview_calls, 0)

    @override_settings(OUTFITS_PREVIEW_ENABLED=True, OUTFITS_PREVIEW_MAX_REQUESTS=1)
    def test_preview_budget_survives_a_change_of_pair(self):
        _, first = self.start()
        self.assertEqual(self.client.post(self.preview_url(first)).status_code, 200)
        self.top.delete()
        self.item(self.owner, "Kemeja baru", "Kemeja")
        _, second = self.start()
        self.assertEqual(self.client.post(self.preview_url(second)).status_code, 429)
        self.assertEqual(self.remote.preview_calls, 1)
        self.assertEqual(OutfitUserPreviewBudget.objects.get().attempts, 1)

    def test_valid_owned_ids_with_nonfinite_score_or_swapped_categories_are_rejected(self):
        _, first = self.start()
        api = first.result["api"]
        for top, bottom, score in ((api["top"]["api_id"], api["bottom"]["api_id"], float("nan")),
                                   (api["bottom"]["api_id"], api["top"]["api_id"], 0.5)):
            self.remote.malformed = {"mode": "best", "results": [{"baju_id": top, "celana_id": bottom, "score": score}]}
            response, conversation = self.start()
            self.assertEqual(response.status_code, 503)
            self.assertIsNone(conversation)
        self.assertEqual(Conversation.objects.count(), 1)


    @override_settings(OUTFITS_PREVIEW_ENABLED=True, OUTFITS_PREVIEW_MAX_REQUESTS=20)
    def test_new_match_starts_preview_once_and_refresh_or_replay_only_reads(self):
        key = uuid4()
        response, conversation = self.start(key=key)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.remote.preview_calls, 1)
        self.assertEqual(OutfitUserPreviewBudget.objects.get(owner=self.owner).attempts, 1)
        self.assertEqual(conversation.result["api"]["preview_start_status"], "queued")
        for _ in range(3):
            self.client.get(self.url(conversation))
            self.client.get(self.preview_url(conversation))
        self.start(key=key)
        self.assertEqual(self.remote.preview_calls, 1)
        self.assertEqual(conversation.messages.count(), 2)

    @override_settings(OUTFITS_PREVIEW_ENABLED=True, OUTFITS_PREVIEW_MAX_REQUESTS=20)
    def test_twenty_attempt_limit_is_per_user_not_global(self):
        OutfitUserPreviewBudget.objects.create(owner=self.owner, attempts=20)
        _, conversation = self.start()
        self.assertEqual(conversation.result["api"]["preview_start_status"], "limit_reached")
        self.assertEqual(self.remote.preview_calls, 0)
        self.item(self.other, "Celana pengguna lain", "Celana")
        self.client.force_login(self.other)
        response = self.client.post(self.index, {"prompt": "best", "request_key": uuid4()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.remote.preview_calls, 1)
        self.assertEqual(OutfitUserPreviewBudget.objects.get(owner=self.owner).attempts, 20)
        self.assertEqual(OutfitUserPreviewBudget.objects.get(owner=self.other).attempts, 1)

    @override_settings(OUTFITS_PREVIEW_ENABLED=True, OUTFITS_PREVIEW_MAX_REQUESTS=20)
    def test_twentieth_attempt_is_allowed_and_twenty_first_is_rejected(self):
        OutfitUserPreviewBudget.objects.create(owner=self.owner, attempts=19)
        _, first = self.start()
        self.assertEqual(self.remote.preview_calls, 1)
        self.assertEqual(OutfitUserPreviewBudget.objects.get(owner=self.owner).attempts, 20)
        self.top.delete()
        self.item(self.owner, "Baju berikutnya", "Kemeja")
        _, second = self.start()
        self.assertEqual(second.result["api"]["preview_start_status"], "limit_reached")
        self.assertEqual(self.remote.preview_calls, 1)

    @override_settings(OUTFITS_PREVIEW_ENABLED=True, OUTFITS_PREVIEW_MAX_REQUESTS=20)
    def test_generation_timeout_never_auto_retries_on_refresh_or_new_same_pair(self):
        with patch.object(self.remote, "preview", side_effect=WardrobeAPIError(code="timeout")) as generate:
            _, conversation = self.start()
            self.client.get(self.url(conversation))
            self.client.get(self.preview_url(conversation))
            self.start()
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(OutfitUserPreviewBudget.objects.get(owner=self.owner).attempts, 1)
        self.assertEqual(self.client.get(self.preview_url(conversation)).json()["preview_status"], "failed_or_unknown")

    @override_settings(OUTFITS_PREVIEW_ENABLED=True, OUTFITS_PREVIEW_MAX_REQUESTS=20)
    def test_status_reads_handle_queued_running_ready_stale_and_failed_without_generate(self):
        _, conversation = self.start()
        job = next(iter(self.remote.jobs.values()))
        for state in ("queued", "running", "ready", "stale", "failed_or_unknown"):
            job["preview_status"] = state
            response = self.client.get(self.preview_url(conversation))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["preview_status"], state)
        self.assertEqual(self.remote.preview_calls, 1)


@override_settings(WARDROBE_API_URL="https://wardrobe.example", WARDROBE_SECRET="test-only-secret-" * 3, OUTFITS_API_TIMEOUT_SECONDS=1)
class APITransportContractTests(SimpleTestCase):
    def test_catalog_validates_shape_status_ids_revision_and_uniqueness(self):
        client = WardrobeAPIClient()
        row = {"item_id": "top-1", "category": "baju", "revision": "revision-1", "status": "ready"}
        with patch.object(client, "request", return_value={"results": [row]}):
            self.assertEqual(client.catalog("owner"), {"top-1": row})
        for data in ({"results": None}, {"results": [{}]}, {"results": [row, row]}, {"results": [{**row, "revision": None}]}):
            with patch.object(client, "request", return_value=data), self.assertRaises(WardrobeAPIError):
                client.catalog("owner")

    def test_upload_replace_delete_and_image_routes_follow_the_contract(self):
        client = WardrobeAPIClient()
        with patch.object(client, "request", return_value={"item_id": "top-1", "status": "ready"}) as request:
            self.assertEqual(client.put("owner", "baju", b"photo"), "top-1")
            request.assert_called_with("owner", "POST", "/v2/items/baju", image=b"photo")
            self.assertEqual(client.put("owner", "baju", b"new", "top-1"), "top-1")
            request.assert_called_with("owner", "PUT", "/v2/items/top-1/baju", image=b"new")
        with patch.object(client, "request", return_value={"item_id": "wrong", "status": "ready"}), self.assertRaises(WardrobeAPIError):
            client.put("owner", "baju", b"photo", "top-1")
        with patch.object(client, "request", return_value=None) as request:
            client.delete("owner", "top-1")
            request.assert_called_with("owner", "DELETE", "/v2/items/top-1", missing_ok=True)
            client.item_image("owner", "top-1")
            request.assert_called_with("owner", "GET", "/v2/items/top-1/image", binary=True)
            client.preview_status("owner", "a" * 64)
            request.assert_called_with("owner", "GET", "/v2/previews/" + "a" * 64, missing_ok=True)
            client.preview_image("owner", "a" * 64)
            request.assert_called_with("owner", "GET", "/v2/previews/" + "a" * 64 + "/image", binary=True)
            client.preview("owner", "top-1", "bottom-1")
            request.assert_called_with("owner", "POST", "/v2/previews", payload={"baju_id": "top-1", "celana_id": "bottom-1"})
        from .api_client import identifier
        for value in (None, "../image", "", "x" * 65):
            with self.assertRaises(WardrobeAPIError): identifier(value)
        with self.assertRaises(WardrobeAPIError): identifier("not-a-preview", preview=True)

    def test_transport_handles_binary_content_types_no_content_and_missing_items(self):
        client = WardrobeAPIClient()
        for path, media in (("/v2/items/top/image", "image/jpeg"), ("/v2/previews/" + "a"*64 + "/image", "image/png")):
            response = BytesIO(b"image-bytes")
            response.status = 200
            response.headers = Headers()
            response.headers["Content-Type"] = media
            with patch("apps.outfits.api_client.build_opener") as opener:
                opener.return_value.open.return_value.__enter__.return_value = response
                self.assertEqual(client.request("owner", "GET", path, binary=True), b"image-bytes")
        response = BytesIO(b"not-image")
        response.status = 200
        response.headers = Headers()
        response.headers["Content-Type"] = "text/html"
        with patch("apps.outfits.api_client.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = response
            with self.assertRaises(WardrobeAPIError): client.item_image("owner", "top")
        response = BytesIO(b"")
        response.status = 204
        with patch("apps.outfits.api_client.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = response
            self.assertIsNone(client.delete("owner", "top"))
        with patch("apps.outfits.api_client.build_opener") as opener:
            opener.return_value.open.side_effect = HTTPError("https://wardrobe.example", 404, "missing", {}, None)
            self.assertIsNone(client.preview_status("owner", "a"*64))

    def test_redirect_handler_never_forwards_signed_requests_to_another_host(self):
        from .api_client import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://external.example"))


class PreviewBudgetMigrationTests(TestCase):
    def test_backfill_preserves_each_owners_consumed_attempts_and_legacy_counter(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from .models import OutfitPreviewBudget
        first = get_user_model().objects.create_user(username="budget-migration-one")
        second = get_user_model().objects.create_user(username="budget-migration-two")
        for owner, total in ((first, 2), (second, 3)):
            account = WardrobeAPIAccount.objects.create(owner=owner, endpoint="https://wardrobe.example")
            for number in range(total):
                OutfitPreviewAttempt.objects.create(account=account, pair_key=str(number))
        OutfitPreviewBudget.objects.create(pk=1, attempts=5)
        migration = import_module("apps.outfits.migrations.0003_outfituserpreviewbudget")
        migration.preserve_attempt_counts(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
        self.assertEqual(OutfitUserPreviewBudget.objects.get(owner=first).attempts, 2)
        self.assertEqual(OutfitUserPreviewBudget.objects.get(owner=second).attempts, 3)
        self.assertEqual(OutfitPreviewBudget.objects.get(pk=1).attempts, 5)
