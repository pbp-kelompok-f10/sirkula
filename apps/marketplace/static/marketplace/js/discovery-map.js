(function () {
  "use strict";

  const app = document.getElementById("discovery-app");
  if (!app || typeof window.maplibregl === "undefined") return;

  const elements = {
    map: document.getElementById("discovery-map"),
    mapMessage: document.getElementById("map-loading-message"),
    locate: document.getElementById("locate-me"),
    search: document.getElementById("location-search"),
    radius: document.getElementById("radius-slider"),
    radiusOutput: document.getElementById("radius-output"),
    status: document.getElementById("discovery-status"),
    locationList: document.getElementById("location-list"),
    storeList: document.getElementById("store-list"),
    storeCount: document.getElementById("store-count"),
    productGrid: document.getElementById("product-grid"),
    productCount: document.getElementById("product-count"),
    storesHeading: document.querySelector(".nearby-panel-heading p"),
    openSavedPlaceDialog: document.getElementById("open-saved-place-dialog"),
    savedPlaceList: document.getElementById("saved-place-list"),
    savedPlaceCount: document.getElementById("saved-place-count"),
    savedPlaceDialog: document.getElementById("saved-place-dialog"),
    savedPlaceForm: document.getElementById("saved-place-form"),
    savedPlaceDialogTitle: document.getElementById("saved-place-dialog-title"),
    savedPlaceId: document.getElementById("saved-place-id"),
    savedPlaceName: document.getElementById("saved-place-name"),
    savedPlaceAddress: document.getElementById("saved-place-address"),
    savedPlaceNotes: document.getElementById("saved-place-notes"),
    savedPlaceLatitude: document.getElementById("saved-place-latitude"),
    savedPlaceLongitude: document.getElementById("saved-place-longitude"),
    savedPlaceFormError: document.getElementById("saved-place-form-error"),
    savedPlaceSubmit: document.getElementById("saved-place-submit"),
  };

  const state = {
    latitude: Number(app.dataset.initialLatitude),
    longitude: Number(app.dataset.initialLongitude),
    radius: Number(app.dataset.initialRadius),
    label: "Jakarta Pusat",
    locationSlug: null,
    requestController: null,
    searchController: null,
    markers: [],
    savedPlaces: [],
    savedPlaceMarkers: [],
    isAuthenticated: app.dataset.isAuthenticated === "true",
  };

  const map = new window.maplibregl.Map({
    container: elements.map,
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [state.longitude, state.latitude],
    zoom: 13,
    attributionControl: true,
  });
  map.addControl(new window.maplibregl.NavigationControl({ showCompass: false }), "top-right");

  const centerMarkerElement = document.createElement("span");
  centerMarkerElement.className = "map-center-marker";
  const centerMarker = new window.maplibregl.Marker({ element: centerMarkerElement })
    .setLngLat([state.longitude, state.latitude])
    .setPopup(new window.maplibregl.Popup({ offset: 14 }).setText("Pusat pencarian"))
    .addTo(map);

  // maaf ini ak ketemu di gugel aku ga jago geografi
  function circleGeoJson(latitude, longitude, radiusKm) {
    const coordinates = [];
    const angularDistance = radiusKm / 6371.0088;
    const latitudeRadians = (latitude * Math.PI) / 180;
    const longitudeRadians = (longitude * Math.PI) / 180;
    for (let step = 0; step <= 72; step += 1) {
      const bearing = (step / 72) * Math.PI * 2;
      const pointLatitude = Math.asin(
        Math.sin(latitudeRadians) * Math.cos(angularDistance) +
          Math.cos(latitudeRadians) * Math.sin(angularDistance) * Math.cos(bearing)
      );
      const pointLongitude =
        longitudeRadians +
        Math.atan2(
          Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitudeRadians),
          Math.cos(angularDistance) - Math.sin(latitudeRadians) * Math.sin(pointLatitude)
        );
      coordinates.push([(pointLongitude * 180) / Math.PI, (pointLatitude * 180) / Math.PI]);
    }
    return {
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [coordinates] },
      properties: {},
    };
  }

  function updateRadiusCircle() {
    const source = map.getSource("search-radius");
    if (source) source.setData(circleGeoJson(state.latitude, state.longitude, state.radius));
  }

  map.on("load", () => {
    map.addSource("search-radius", {
      type: "geojson",
      data: circleGeoJson(state.latitude, state.longitude, state.radius),
    });
    map.addLayer({
      id: "search-radius-fill",
      type: "fill",
      source: "search-radius",
      paint: { "fill-color": "#2d734c", "fill-opacity": 0.2 },
    });
    map.addLayer({
      id: "search-radius-line",
      type: "line",
      source: "search-radius",
      paint: { "line-color": "#2d734c", "line-width": 2 },
    });
    elements.map.querySelector(".map-placeholder")?.remove();
    elements.mapMessage?.remove();
  });

  function debounce(callback, delay) {
    let timeout;
    return function (...args) {
      window.clearTimeout(timeout);
      timeout = window.setTimeout(() => callback.apply(this, args), delay);
    };
  }

  function setStatus(message, isError) {
    elements.status.textContent = message;
    elements.status.classList.toggle("is-error", Boolean(isError));
  }

  function setBusy(isBusy) {
    app.classList.toggle("is-loading", isBusy);
    app.setAttribute("aria-busy", String(isBusy));
  }

  function updateCenter(latitude, longitude, label, options) {
    state.latitude = Number(latitude);
    state.longitude = Number(longitude);
    state.label = label || "Lokasi dipilih";
    state.locationSlug = options?.locationSlug || null;
    const point = [state.longitude, state.latitude];
    updateRadiusCircle();
    centerMarker
      .setLngLat(point)
      .setPopup(new window.maplibregl.Popup({ offset: 14 }).setText(state.label));
    map.flyTo({ center: point, zoom: options?.zoom || 13, duration: 600 });
    updateSelectedLocation(state.locationSlug);
  }

  function clearResultMarkers() {
    state.markers.forEach((marker) => marker.remove());
    state.markers = [];
  }

  function createResultMarker(item, type) {
    const isStore = type === "store";
    const markerElement = document.createElement("span");
    markerElement.className = `map-result-marker ${isStore ? "is-store" : "is-listing"}`;
    const popup = new window.maplibregl.Popup({ offset: 14 }).setHTML(
      `<strong>${escapeHtml(item.name || item.title)}</strong><br>${Number(item.distance_km).toFixed(1)} km`
    );
    const marker = new window.maplibregl.Marker({ element: markerElement })
      .setLngLat([item.longitude, item.latitude])
      .setPopup(popup)
      .addTo(map);
    state.markers.push(marker);
  }

  function escapeHtml(value) {
    const node = document.createElement("span");
    node.textContent = String(value ?? "");
    return node.innerHTML;
  }

  function formatPrice(value) {
    if (value === null || value === undefined) return "Tukar barang";
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(Number(value));
  }

  function emptyState(message, extraClass) {
    const node = document.createElement("div");
    node.className = `discovery-empty-state${extraClass ? ` ${extraClass}` : ""}`;
    node.textContent = message;
    return node;
  }

  function savedPlaceDetailUrl(id) {
    return app.dataset.savedPlaceUrlTemplate.replace("/0/", `/${id}/`);
  }

  function csrfToken() {
    return elements.savedPlaceForm?.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  }

  function clearSavedPlaceMarkers() {
    state.savedPlaceMarkers.forEach((marker) => marker.remove());
    state.savedPlaceMarkers = [];
  }

  function createSavedPlaceMarker(place) {
    const markerElement = document.createElement("button");
    markerElement.type = "button";
    markerElement.className = "map-saved-place-marker";
    markerElement.setAttribute("aria-label", `Tempat tersimpan: ${place.name}`);
    const popup = new window.maplibregl.Popup({ offset: 20 }).setText(
      `${place.name} — ${place.address_label}`
    );
    const marker = new window.maplibregl.Marker({ element: markerElement })
      .setLngLat([place.longitude, place.latitude])
      .setPopup(popup)
      .addTo(map);
    state.savedPlaceMarkers.push(marker);
  }

  function createSavedPlaceAction(action, label, text, extraClass) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `saved-place-action${extraClass ? ` ${extraClass}` : ""}`;
    button.dataset.action = action;
    button.setAttribute("aria-label", label);
    button.textContent = text;
    return button;
  }

  function renderSavedPlaces(places) {
    state.savedPlaces = places;
    elements.savedPlaceList.replaceChildren();
    clearSavedPlaceMarkers();

    places.forEach((place) => {
      const article = document.createElement("article");
      article.className = "saved-place-card";
      article.dataset.savedPlaceId = String(place.id);

      const main = document.createElement("button");
      main.type = "button";
      main.className = "saved-place-main";
      main.dataset.action = "focus";
      const name = document.createElement("strong");
      name.textContent = place.name;
      const address = document.createElement("small");
      address.textContent = place.address_label;
      main.append(name, address);

      const actions = document.createElement("div");
      actions.className = "saved-place-actions";
      actions.append(
        createSavedPlaceAction("edit", `Edit ${place.name}`, "✎"),
        createSavedPlaceAction("delete", `Hapus ${place.name}`, "×", "is-delete")
      );

      article.append(main, actions);
      elements.savedPlaceList.append(article);
      createSavedPlaceMarker(place);
    });

    if (!places.length) {
      elements.savedPlaceList.append(
        emptyState("Belum ada tempat tersimpan. Pilih titik pada peta lalu simpan.")
      );
    }
    elements.savedPlaceCount.textContent = `${places.length} tempat`;
  }

  async function loadSavedPlaces() {
    if (!state.isAuthenticated) return;
    try {
      const response = await fetch(app.dataset.savedPlacesUrl, {
        headers: { Accept: "application/json" },
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error?.message || "Tempat tersimpan tidak dapat dimuat.");
      renderSavedPlaces(payload.results);
    } catch (error) {
      elements.savedPlaceList.replaceChildren(emptyState(error.message));
      setStatus(error.message, true);
    }
  }

  function openSavedPlaceForm(place) {
    if (!state.isAuthenticated || !elements.savedPlaceDialog) {
      setStatus("Login diperlukan untuk menyimpan tempat.", true);
      return;
    }

    const isEditing = Boolean(place);
    elements.savedPlaceForm.reset();
    elements.savedPlaceId.value = isEditing ? String(place.id) : "";
    elements.savedPlaceName.value = place?.name || "";
    elements.savedPlaceAddress.value = place?.address_label || state.label;
    elements.savedPlaceNotes.value = place?.notes || "";
    elements.savedPlaceLatitude.value = String(place?.latitude ?? state.latitude);
    elements.savedPlaceLongitude.value = String(place?.longitude ?? state.longitude);
    elements.savedPlaceDialogTitle.textContent = isEditing ? "Edit tempat tersimpan" : "Simpan tempat";
    elements.savedPlaceSubmit.textContent = isEditing ? "Simpan perubahan" : "Simpan tempat";
    elements.savedPlaceFormError.hidden = true;
    elements.savedPlaceDialog.showModal();
    elements.savedPlaceName.focus();
  }

  function closeSavedPlaceForm() {
    elements.savedPlaceDialog?.close();
  }

  function savedPlacePayload() {
    return {
      name: elements.savedPlaceName.value,
      address_label: elements.savedPlaceAddress.value,
      notes: elements.savedPlaceNotes.value,
      latitude: elements.savedPlaceLatitude.value,
      longitude: elements.savedPlaceLongitude.value,
    };
  }

  function formErrorMessage(payload) {
    const fields = payload.error?.fields;
    if (fields) {
      const firstField = Object.values(fields)[0];
      if (Array.isArray(firstField) && firstField[0]?.message) return firstField[0].message;
    }
    return payload.error?.message || "Tempat tidak dapat disimpan.";
  }

  async function submitSavedPlace(event) {
    event.preventDefault();
    const id = elements.savedPlaceId.value;
    const isEditing = Boolean(id);
    const url = isEditing ? savedPlaceDetailUrl(id) : app.dataset.savedPlacesUrl;
    elements.savedPlaceSubmit.disabled = true;
    elements.savedPlaceFormError.hidden = true;

    try {
      const response = await fetch(url, {
        method: isEditing ? "PUT" : "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify(savedPlacePayload()),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(formErrorMessage(payload));
      closeSavedPlaceForm();
      await loadSavedPlaces();
      setStatus(isEditing ? "Tempat tersimpan berhasil diperbarui." : "Titik berhasil disimpan.");
    } catch (error) {
      elements.savedPlaceFormError.textContent = error.message;
      elements.savedPlaceFormError.hidden = false;
    } finally {
      elements.savedPlaceSubmit.disabled = false;
    }
  }

  async function deleteSavedPlace(place) {
    if (!window.confirm(`Hapus “${place.name}” dari tempat tersimpan?`)) return;
    try {
      const response = await fetch(savedPlaceDetailUrl(place.id), {
        method: "DELETE",
        headers: { Accept: "application/json", "X-CSRFToken": csrfToken() },
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error?.message || "Tempat tidak dapat dihapus.");
      await loadSavedPlaces();
      setStatus("Tempat tersimpan berhasil dihapus.");
    } catch (error) {
      setStatus(error.message, true);
    }
  }

  function renderStores(stores) {
    elements.storeList.replaceChildren();
    stores.forEach((store, index) => {
      const article = document.createElement("article");
      article.className = `store-result${index === 0 ? " is-featured" : ""}`;

      const rank = document.createElement("span");
      rank.className = "store-rank";
      rank.textContent = String(index + 1);

      const copy = document.createElement("div");
      copy.className = "store-result-copy";
      const title = document.createElement("h4");
      title.textContent = store.name;
      const meta = document.createElement("p");
      meta.textContent = `${Number(store.distance_km).toFixed(1)} km • ${store.address}`;
      copy.append(title, meta);

      const open = document.createElement("span");
      open.className = "store-open-label";
      open.textContent = "Buka";
      article.append(rank, copy, open);
      elements.storeList.append(article);
      createResultMarker(store, "store");
    });
    if (!stores.length) elements.storeList.append(emptyState("Belum ada toko di dalam radius ini."));
    elements.storeCount.textContent = `${stores.length} hasil`;
  }

  function renderProducts(listings) {
    elements.productGrid.replaceChildren();
    listings.forEach((listing) => {
      const article = document.createElement("article");
      article.className = "card-product discovery-product-card";

      const figure = document.createElement("div");
      figure.className = "card-figure";
      if (listing.image_url) {
        const image = document.createElement("img");
        image.src = listing.image_url;
        image.alt = listing.title;
        image.loading = "lazy";
        figure.append(image);
      } else {
        const placeholder = document.createElement("div");
        placeholder.className = "product-image-placeholder";
        figure.append(placeholder);
      }
      const label = document.createElement("span");
      label.className = "card-label";
      label.textContent = listing.listing_type_label;
      figure.append(label);

      const body = document.createElement("div");
      body.className = "card-body";
      const description = document.createElement("span");
      description.className = "card-description";
      description.textContent = `${Number(listing.distance_km).toFixed(1)} km • ${listing.store.name}`;
      const title = document.createElement("h3");
      title.className = "card-title";
      title.textContent = listing.title;
      const price = document.createElement("span");
      price.className = "card-price";
      price.textContent = formatPrice(listing.price);
      const actions = document.createElement("div");
      actions.className = "card-actions";
      const detail = document.createElement("button");
      detail.type = "button";
      detail.className = "btn btn-primary";
      detail.textContent = "Lihat Detail";
      const save = document.createElement("button");
      save.type = "button";
      save.className = "btn btn-outline btn-primary btn-square";
      save.setAttribute("aria-label", `Simpan ${listing.title}`);
      save.textContent = "♡";
      actions.append(detail, save);
      body.append(description, title, price, actions);
      article.append(figure, body);
      elements.productGrid.append(article);
      createResultMarker(listing, "listing");
    });
    if (!listings.length) {
      elements.productGrid.append(emptyState("Belum ada produk di dalam radius ini.", "product-empty-state"));
    }
    elements.productCount.textContent = `${listings.length} produk`;
  }

  function updateSelectedLocation(slug) {
    elements.locationList.querySelectorAll(".location-card").forEach((card) => {
      const selected = Boolean(slug) && card.dataset.locationSlug === slug;
      card.classList.toggle("is-selected", selected);
      card.setAttribute("aria-pressed", String(selected));
      const oldLabel = card.querySelector(".location-selected-label");
      if (oldLabel && !selected) {
        oldLabel.className = "location-type-label";
        oldLabel.textContent = "Wilayah";
      } else if (!oldLabel && selected) {
        const typeLabel = card.querySelector(".location-type-label");
        if (typeLabel) {
          typeLabel.className = "location-selected-label";
          typeLabel.textContent = "Dipilih";
        }
      }
    });
  }

  async function loadNearby(options) {
    state.requestController?.abort();
    const controller = new AbortController();
    state.requestController = controller;
    const parameters = new URLSearchParams({ radius: String(state.radius) });
    if (options?.useIpFallback) {
      // Omitting coordinates instructs the backend to resolve the request IP.
    } else if (state.locationSlug) {
      parameters.set("location", state.locationSlug);
    } else {
      parameters.set("lat", String(state.latitude));
      parameters.set("lon", String(state.longitude));
      parameters.set("label", state.label);
    }

    setBusy(true);
    setStatus("Memperbarui hasil terdekat…");
    try {
      const response = await fetch(`${app.dataset.nearbyUrl}?${parameters}`, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error?.message || "Hasil tidak dapat dimuat.");

      if (options?.useIpFallback) {
        updateCenter(payload.center.latitude, payload.center.longitude, payload.center.label, { zoom: 13 });
      }
      clearResultMarkers();
      renderStores(payload.stores);
      renderProducts(payload.listings);
      elements.storesHeading.textContent = `Berdasarkan radius ${payload.radius_km} km dari ${payload.center.label}`;
      setStatus(`Menampilkan ${payload.counts.listings} produk dan ${payload.counts.stores} toko di sekitar ${payload.center.label}.`);
    } catch (error) {
      if (error.name !== "AbortError") setStatus(error.message, true);
    } finally {
      if (state.requestController === controller && !controller.signal.aborted) setBusy(false);
    }
  }

  const loadNearbyDebounced = debounce(() => loadNearby(), 350);

  async function reverseSelectedPoint(latitude, longitude) {
    const parameters = new URLSearchParams({ lat: latitude, lon: longitude });
    try {
      const response = await fetch(`${app.dataset.reverseGeocodeUrl}?${parameters}`, {
        headers: { Accept: "application/json" },
      });
      const payload = await response.json();
      return response.ok ? payload.result.label : "Lokasi dipilih";
    } catch (_error) {
      return "Lokasi dipilih";
    }
  }

  async function selectMapPoint(latitude, longitude) {
    setStatus("Mencari alamat titik yang dipilih…");
    const label = await reverseSelectedPoint(latitude, longitude);
    updateCenter(latitude, longitude, label, { zoom: 14 });
    loadNearby();
  }

  function renderLocationCards(locations) {
    elements.locationList.replaceChildren();
    locations.forEach((location) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "location-card";
      card.dataset.locationSlug = location.slug || "";
      card.dataset.latitude = location.latitude;
      card.dataset.longitude = location.longitude;
      const selected = Boolean(location.slug) && location.slug === state.locationSlug;
      card.classList.toggle("is-selected", selected);
      card.setAttribute("aria-pressed", String(selected));

      const copy = document.createElement("span");
      copy.className = "location-card-copy";
      const name = document.createElement("strong");
      name.textContent = location.name || location.label;
      const address = document.createElement("small");
      address.textContent = location.address || location.label;
      copy.append(name, address);

      const badge = document.createElement("span");
      badge.className = selected ? "location-selected-label" : "location-type-label";
      badge.textContent = selected
        ? "Dipilih"
        : location.region_type === "regency"
          ? "Kabupaten"
          : location.region_type === "city"
            ? "Kota"
            : "Hasil pencarian";
      card.append(copy, badge);
      elements.locationList.append(card);
    });
    if (!locations.length) {
      elements.locationList.append(emptyState("Tidak ada lokasi yang sesuai dengan pencarian."));
    }
  }

  async function searchLocations(query) {
    state.searchController?.abort();
    const controller = new AbortController();
    state.searchController = controller;
    const normalizedQuery = query.trim();
    const parameters = new URLSearchParams({ q: normalizedQuery });
    elements.locationList.replaceChildren(emptyState("Mencari lokasi…"));

    try {
      const predefinedRequest = fetch(`${app.dataset.locationsUrl}?${parameters}`, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });

      const geocodeRequest = normalizedQuery.length >= 3
        ? fetch(`${app.dataset.geocodeUrl}?${parameters}`, {
            headers: { Accept: "application/json" },
            signal: controller.signal,
          })
        : null;

      const predefinedResponse = await predefinedRequest;
      if (!predefinedResponse.ok) throw new Error("Daftar lokasi tidak dapat dimuat.");
      const predefinedPayload = await predefinedResponse.json();
      let locations = predefinedPayload.results;

      if (geocodeRequest) {
        const geocodeResponse = await geocodeRequest;
        if (geocodeResponse.ok) {
          const geocodePayload = await geocodeResponse.json();
          const predefinedCoordinates = new Set(
            locations.map((location) => `${Number(location.latitude).toFixed(4)}:${Number(location.longitude).toFixed(4)}`)
          );
          const additionalLocations = geocodePayload.results
            .filter((location) => !predefinedCoordinates.has(
              `${Number(location.latitude).toFixed(4)}:${Number(location.longitude).toFixed(4)}`
            ))
            .map((location) => ({ ...location, name: location.label, address: location.label }));
          locations = locations.concat(additionalLocations);
        }
      }

      renderLocationCards(locations.slice(0, 10));
      setStatus(
        normalizedQuery
          ? `Menampilkan ${locations.length} lokasi untuk “${normalizedQuery}”.`
          : "Menampilkan seluruh lokasi JABODETABEK."
      );
    } catch (error) {
      if (error.name !== "AbortError") {
        elements.locationList.replaceChildren(emptyState("Lokasi tidak dapat dimuat."));
        setStatus(error.message, true);
      }
    }
  }

  function requestUserLocation() {
    if (!("geolocation" in navigator)) {
      setStatus("Geolocation tidak didukung. Menggunakan perkiraan lokasi dari IP.");
      loadNearby({ useIpFallback: true });
      return;
    }
    setStatus("Meminta izin lokasi…");
    navigator.geolocation.getCurrentPosition(
      (position) => selectMapPoint(position.coords.latitude, position.coords.longitude),
      () => {
        setStatus("Izin lokasi tidak diberikan. Menggunakan perkiraan lokasi dari IP.");
        loadNearby({ useIpFallback: true });
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 300000 }
    );
  }

  elements.locationList.addEventListener("click", (event) => {
    const card = event.target.closest(".location-card");
    if (!card) return;
    const label = card.querySelector("strong")?.textContent || "Lokasi dipilih";
    updateCenter(card.dataset.latitude, card.dataset.longitude, label, {
      locationSlug: card.dataset.locationSlug,
      zoom: 12,
    });
    loadNearby();
  });

  elements.radius.addEventListener("input", () => {
    state.radius = Number(elements.radius.value);
    elements.radiusOutput.textContent = `${state.radius} km`;
    updateRadiusCircle();
    loadNearbyDebounced();
  });

  elements.search.addEventListener("input", debounce((event) => searchLocations(event.target.value), 350));
  elements.locate.addEventListener("click", requestUserLocation);
  elements.openSavedPlaceDialog.addEventListener("click", () => openSavedPlaceForm());
  elements.savedPlaceForm?.addEventListener("submit", submitSavedPlace);
  elements.savedPlaceDialog?.querySelectorAll("[data-close-saved-place-dialog]").forEach((button) => {
    button.addEventListener("click", closeSavedPlaceForm);
  });
  elements.savedPlaceList.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]");
    const card = event.target.closest("[data-saved-place-id]");
    if (!action || !card) return;
    const place = state.savedPlaces.find((item) => item.id === Number(card.dataset.savedPlaceId));
    if (!place) return;
    if (action.dataset.action === "edit") openSavedPlaceForm(place);
    if (action.dataset.action === "delete") deleteSavedPlace(place);
    if (action.dataset.action === "focus") {
      updateCenter(place.latitude, place.longitude, place.name, { zoom: 14 });
      loadNearby();
    }
  });
  map.on("click", (event) => selectMapPoint(event.lngLat.lat, event.lngLat.lng));

  loadSavedPlaces();
  // Minta permissions buat akses lokasi, kalau gak dikasih bakal pake lokasi dari IP
  requestUserLocation();
})();
