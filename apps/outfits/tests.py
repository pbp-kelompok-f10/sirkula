from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem
from .demo_data import DEMO_RECOMMENDATIONS
from .models import Conversation, Message
from .providers import DemoStylistProvider
from .services import get_landing_content, send_message


class OutfitsConversationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="chat-owner")
        self.other = get_user_model().objects.create_user(username="chat-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.index = reverse("outfits:index")
        self.client.force_login(self.owner)

    def start(self, prompt="Outfit kuliah", key=None, **extra):
        key = key or uuid4()
        response = self.client.post(self.index, {"prompt": prompt, "request_key": key, **extra})
        conversation = Conversation.objects.filter(owner=self.owner, creation_key=key).first()
        return response, conversation

    def url(self, conversation):
        return reverse("outfits:conversation", kwargs={"conversation_id": conversation.pk})

    def post_message(self, conversation, prompt="Bisa lebih santai?", key=None, version=None, **extra):
        return self.client.post(self.url(conversation), {
            "prompt": prompt, "request_key": key or uuid4(),
            "version": version if version is not None else conversation.version,
            **extra,
        }, HTTP_ACCEPT="application/json")

    def test_public_landing_has_requested_sections_without_fake_private_history(self):
        self.client.logout()
        response = self.client.get(self.index)
        self.assertEqual(response.status_code, 200)
        for text in ("Mix and Match", "Ke Lemari Virtual", "Rekomendasi Outfit", "Riwayat", "Belum ada riwayat."):
            self.assertContains(response, text)
        self.assertContains(response, 'class="mix-card"', count=4)
        for text in ("Outfit Tersimpan", "Simpan Outfit", "Acak Outfit", "Chat Baru"):
            self.assertNotContains(response, text)
        self.assertContains(response, 'aria-label="Kirim kebutuhan outfit"')
        self.assertEqual(response.context["history"], [])

    def test_prompt_starts_owned_conversation_and_redirects_with_filter(self):
        response, conversation = self.start("  Kemeja biru untuk kuliah  ", category=self.category.pk, owner=self.other.pk)
        self.assertRedirects(response, self.url(conversation) + f"?category={self.category.pk}")
        self.assertEqual(conversation.owner, self.owner)
        self.assertEqual(conversation.version, 1)
        self.assertEqual(list(conversation.messages.values_list("role", flat=True)), ["user", "assistant"])
        self.assertEqual(conversation.messages.first().content, "Kemeja biru untuk kuliah")
        self.assertEqual(conversation.result["mode"], "demo")
        self.assertEqual(len(conversation.result["pieces"]), 3)

    def test_recommendation_card_starts_canonical_prompt_not_forged_content(self):
        entry = DEMO_RECOMMENDATIONS[0]
        response, conversation = self.start("Forged", recommendation=entry["id"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(conversation.initial_recommendation, entry["id"])
        self.assertEqual(conversation.messages.first().content, f"Tolong buatkan outfit dengan {entry['title'].lower()}.")

    def test_invalid_prompt_key_and_recommendation_do_not_create_rows(self):
        for data in (
            {"prompt": ""}, {"prompt": "   "}, {"prompt": "x" * 501},
            {"request_key": "bad"}, {"recommendation": "not-a-card"},
        ):
            with self.subTest(data=data):
                response = self.client.post(self.index, {"prompt": "Kuliah", "request_key": uuid4(), **data})
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_anonymous_start_is_forbidden_without_creating_records(self):
        self.client.logout()
        response, _ = self.start()
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Silakan login", status_code=403)
        self.assertFalse(Conversation.objects.exists())

    def test_workspace_reopens_all_messages_result_and_private_cache_headers(self):
        _, conversation = self.start()
        self.post_message(conversation)
        response = self.client.get(self.url(conversation))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["chat_messages"]), 4)
        for text in ("SirkulaAI", "Preview outfit", "Kaos putih", "Kemeja biru", "Celana krem", "Chat Baru"):
            self.assertContains(response, text)
        self.assertContains(response, 'id="chat-history-toggle"')
        self.assertContains(response, 'id="chat-prompt"')
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])
        self.assertEqual(self.client.head(self.url(conversation)).status_code, 200)

    def test_other_user_and_anonymous_cannot_read_or_write_conversation(self):
        _, conversation = self.start("Rahasia pemilik")
        for user in (self.other, None):
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            for method in ("get", "post"):
                with self.subTest(user=user, method=method):
                    response = getattr(self.client, method)(self.url(conversation), {"prompt": "ubah", "version": 1, "request_key": uuid4()})
                    self.assertEqual(response.status_code, 404)
                    self.assertNotContains(response, "Rahasia pemilik", status_code=404)
        self.assertEqual(conversation.messages.count(), 2)

    def test_unknown_conversation_is_not_found(self):
        response = self.client.get(reverse("outfits:conversation", kwargs={"conversation_id": uuid4()}))
        self.assertEqual(response.status_code, 404)

    def test_history_only_contains_current_user_and_new_chat_does_not_delete_it(self):
        _, first = self.start("Kuliah milikku")
        self.client.force_login(self.other)
        self.client.post(self.index, {"prompt": "Rahasia pengguna lain", "request_key": uuid4()})
        self.client.force_login(self.owner)
        response = self.client.get(self.index)
        self.assertEqual([row.pk for row in response.context["history"]], [first.pk])
        self.assertNotContains(response, "Rahasia pengguna lain")
        response = self.client.get(self.url(first))
        self.assertNotContains(response, "Rahasia pengguna lain")
        self.assertContains(response, 'class="chat-new"')
        self.client.get(self.index + "#mix-prompt")
        self.assertEqual(Conversation.objects.count(), 2)
        self.assertEqual(first.messages.count(), 2)

    def test_history_is_sorted_by_latest_message(self):
        _, first = self.start("Pertama")
        _, second = self.start("Kedua")
        self.post_message(first)
        response = self.client.get(self.index)
        self.assertEqual([row.pk for row in response.context["history"]], [first.pk, second.pk])
        self.assertContains(response, self.url(first))

    def test_send_message_adds_one_pair_updates_version_and_uses_bounded_history(self):
        _, conversation = self.start()
        provider = DemoStylistProvider()
        with patch("apps.outfits.services.get_stylist_provider", return_value=provider):
            with patch.object(provider, "reply", wraps=provider.reply) as reply:
                response = self.post_message(conversation)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        conversation.refresh_from_db()
        self.assertEqual(conversation.version, 2)
        self.assertEqual(conversation.messages.count(), 4)
        self.assertEqual([entry["role"] for entry in reply.call_args.kwargs["history"]], ["user", "assistant"])
        self.assertEqual(list(conversation.messages.values_list("sequence", flat=True)), [1, 2, 3, 4])
        for _ in range(11):
            response = self.post_message(conversation)
            self.assertEqual(response.status_code, 200)
            conversation.refresh_from_db()
        with patch("apps.outfits.services.get_stylist_provider", return_value=provider):
            with patch.object(provider, "reply", wraps=provider.reply) as reply:
                self.post_message(conversation)
        self.assertEqual(len(reply.call_args.kwargs["history"]), 20)

    def test_html_fallback_send_redirects_to_get(self):
        _, conversation = self.start()
        response = self.client.post(self.url(conversation), {"prompt": "Lebih santai", "request_key": uuid4(), "version": 1})
        self.assertRedirects(response, self.url(conversation))
        self.assertEqual(conversation.messages.count(), 4)

    def test_duplicate_start_and_message_do_not_duplicate_or_call_provider_again(self):
        key = uuid4()
        _, conversation = self.start(key=key)
        with patch("apps.outfits.services.get_stylist_provider") as provider:
            response, replayed = self.start(key=key)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(replayed.pk, conversation.pk)
            provider.assert_not_called()
        key = uuid4()
        self.assertEqual(self.post_message(conversation, key=key).status_code, 200)
        with patch("apps.outfits.services.get_stylist_provider") as provider:
            self.assertEqual(self.post_message(conversation, key=key, version=1).status_code, 200)
            provider.assert_not_called()
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(conversation.messages.count(), 4)

    def test_reusing_key_for_different_content_is_conflict(self):
        key = uuid4()
        _, conversation = self.start(key=key)
        response, _ = self.start("Isi berbeda", key=key)
        self.assertEqual(response.status_code, 409)
        key = uuid4()
        self.post_message(conversation, key=key)
        response = self.post_message(conversation, key=key, prompt="Isi berbeda")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(conversation.messages.count(), 4)

    def test_stale_version_and_missing_or_invalid_hidden_fields_preserve_chat(self):
        _, conversation = self.start()
        self.post_message(conversation)
        response = self.post_message(conversation, key=uuid4(), version=1)
        self.assertEqual(response.status_code, 409)
        for extra in ({"prompt": "  "}, {"prompt": "x" * 501}, {"request_key": "bad"}, {"version": ""}, {"version": -1}):
            response = self.post_message(conversation, **extra)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(conversation.messages.count(), 4)

    def test_start_provider_failure_creates_no_partial_conversation_and_retry_works(self):
        key = uuid4()
        with patch("apps.outfits.services.get_stylist_provider", side_effect=TimeoutError("provider down")):
            with self.assertLogs("apps.outfits.views", level="ERROR"):
                response, _ = self.start(key=key)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(Message.objects.exists())
        response, _ = self.start(key=key)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 2)

    def test_send_provider_failure_preserves_chat_and_same_key_can_retry(self):
        _, conversation = self.start()
        before = deepcopy(conversation.result)
        key = uuid4()
        with patch("apps.outfits.services.get_stylist_provider", side_effect=TimeoutError("provider down")):
            with self.assertLogs("apps.outfits.views", level="ERROR"):
                response = self.post_message(conversation, key=key)
        self.assertEqual(response.status_code, 500)
        conversation.refresh_from_db()
        self.assertEqual(conversation.version, 1)
        self.assertEqual(conversation.result, before)
        self.assertEqual(conversation.messages.count(), 2)
        self.assertEqual(self.post_message(conversation, key=key).status_code, 200)
        self.assertEqual(conversation.messages.count(), 4)

    def test_database_failure_rolls_back_start_and_send_pairs(self):
        with patch.object(Message.objects, "bulk_create", side_effect=IntegrityError("database failed")):
            with self.assertLogs("apps.outfits.views", level="ERROR"):
                response, _ = self.start()
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Conversation.objects.exists())
        _, conversation = self.start()
        before = deepcopy(conversation.result)
        with patch.object(Message.objects, "bulk_create", side_effect=IntegrityError("database failed")):
            with self.assertLogs("apps.outfits.views", level="ERROR"):
                response = self.post_message(conversation)
        self.assertEqual(response.status_code, 500)
        conversation.refresh_from_db()
        self.assertEqual(conversation.result, before)
        self.assertEqual(conversation.version, 1)
        self.assertEqual(conversation.messages.count(), 2)

    def test_version_is_checked_again_after_provider_returns(self):
        _, conversation = self.start()
        provider = DemoStylistProvider()
        reply = provider.reply(prompt="lain", history=())
        called = False
        def concurrent_reply(**kwargs):
            nonlocal called
            if not called:
                called = True
                send_message(user=self.owner, conversation_id=conversation.pk, prompt="Pesan tab lain", key=uuid4(), version=1)
            return reply
        with patch.object(provider, "reply", side_effect=concurrent_reply):
            with patch("apps.outfits.services.get_stylist_provider", return_value=provider):
                response = self.post_message(conversation, prompt="Pesan terlambat")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(conversation.messages.count(), 4)
        self.assertTrue(conversation.messages.filter(content="Pesan tab lain").exists())
        self.assertFalse(conversation.messages.filter(content="Pesan terlambat").exists())

    def test_malformed_provider_result_is_rejected_before_any_write(self):
        provider = DemoStylistProvider()
        reply = provider.reply(prompt="test", history=())
        malformed = deepcopy(reply.result)
        malformed["preview"] = {"kind": "url", "url": "https://external.example/private"}
        for value in (replace(reply, text=""), replace(reply, result=malformed)):
            with patch.object(provider, "reply", return_value=value):
                with patch("apps.outfits.services.get_stylist_provider", return_value=provider):
                    with self.assertLogs("apps.outfits.views", level="ERROR"):
                        response, _ = self.start()
            self.assertEqual(response.status_code, 500)
        self.assertFalse(Conversation.objects.exists())

    def test_csrf_and_http_methods(self):
        _, conversation = self.start()
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        for url in (self.index, self.url(conversation)):
            self.assertEqual(secured.post(url, {"prompt": "test", "request_key": uuid4(), "version": 1}).status_code, 403)
            self.assertEqual(self.client.delete(url).status_code, 405)

    def test_text_is_escaped_in_messages_titles_and_history(self):
        _, conversation = self.start('<script>alert("test")</script>')
        for url in (self.index, self.url(conversation)):
            response = self.client.get(url)
            self.assertNotContains(response, '<script>alert("test")</script>')
            self.assertContains(response, "&lt;script&gt;")

    def test_demo_does_not_read_or_expose_real_wardrobe_items(self):
        for user in (self.owner, self.other):
            WardrobeItem.objects.create(owner=user, name=f"Rahasia aktif {user.username}")
            WardrobeItem.objects.create(owner=user, name=f"Rahasia draft {user.username}", status="draft")
        _, conversation = self.start()
        for url in (self.index, self.url(conversation)):
            response = self.client.get(url)
            self.assertNotContains(response, "Rahasia aktif")
            self.assertNotContains(response, "Rahasia draft")
        self.assertEqual(WardrobeItem.objects.count(), 4)

    def test_demo_provider_is_database_free_and_returns_fresh_data(self):
        provider = DemoStylistProvider()
        with self.assertNumQueries(0):
            reply = provider.reply(prompt="Kasual", history=())
        reply.result["pieces"][0]["name"] = "changed"
        self.assertNotEqual(provider.reply(prompt="Kasual", history=()).result["pieces"][0]["name"], "changed")
        payload = get_landing_content()
        payload["recommendations"][0]["title"] = "changed"
        self.assertNotEqual(get_landing_content()["recommendations"][0]["title"], "changed")

    def test_database_constraints_and_owner_scoped_creation_key(self):
        key = uuid4()
        _, conversation = self.start(key=key)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Conversation.objects.create(owner=self.owner, creation_key=key, title="duplicate")
        self.client.force_login(self.other)
        response = self.client.post(self.index, {"prompt": "Lain", "request_key": key})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Conversation.objects.count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Message.objects.create(conversation=conversation, role="user", content="bad", sequence=1, request_key=uuid4())

    def test_back_navigation_is_safe_and_wardrobe_links_still_keep_category(self):
        response = self.client.get(self.index, {"category": "12"})
        self.assertEqual(response.context["wardrobe_url"], reverse("wardrobe:index") + "?category=12")
        for value in ("https://example.org", "-1", "1&next=bad", "0", "9" * 100, "１２"):
            self.assertEqual(self.client.get(self.index, {"category": value}).context["wardrobe_url"], reverse("wardrobe:index"))
        response = self.client.get(reverse("wardrobe:index"), {"category": self.category.pk})
        self.assertContains(response, f'href="{self.index}?category={self.category.pk}"')
        self.assertContains(response, f'href="{self.index}?category={self.category.pk}#mix-prompt"')

    def test_workspace_assets_are_registered(self):
        for path in ("outfits/css/landing.css", "outfits/css/chat.css", "outfits/js/chat.js", "outfits/img/workspace-reference.png"):
            self.assertIsNotNone(finders.find(path))

    def test_older_conversations_remain_available_beyond_fifty_entries(self):
        result = DemoStylistProvider().reply(prompt="demo", history=()).result
        Conversation.objects.bulk_create([
            Conversation(owner=self.owner, title=f"Riwayat {index}", creation_key=uuid4(), result=deepcopy(result))
            for index in range(51)
        ])
        response = self.client.get(self.index)
        self.assertEqual(len(response.context["history"]), 51)
        self.assertContains(response, "Riwayat 0")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])
