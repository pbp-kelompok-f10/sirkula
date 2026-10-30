from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import MixAndMatchPromptForm
from .services import get_landing_content


@require_http_methods(["GET", "HEAD", "POST"])
def index(request):
    form = MixAndMatchPromptForm(request.POST if request.method == "POST" else None)
    valid = form.is_valid() if form.is_bound else False
    prompt = form.cleaned_data["prompt"] if valid else ""
    category = (request.POST if request.method == "POST" else request.GET).get("category", "")
    if not (
        0 < len(category) <= 10
        and category.isascii()
        and category.isdigit()
        and int(category) > 0
    ):
        category = ""
    wardrobe_url = reverse("wardrobe:index")
    if category:
        wardrobe_url += "?" + urlencode({"category": category})
    context = {
        **get_landing_content(prompt),
        "prompt_form": form,
        "submitted_prompt": prompt,
        "return_category": category,
        "wardrobe_url": wardrobe_url,
    }
    return render(
        request,
        "outfits/index.html",
        context,
        status=400 if form.is_bound and not valid else 200,
    )
