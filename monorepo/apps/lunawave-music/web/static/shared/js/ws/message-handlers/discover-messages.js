import { emit as bus } from "../../bus.js";
import { store } from "/framework/static/js/core/store.js";

export function handleDiscoverMessage(msg) {
    switch (msg.type) {
        case "search_results":
            bus("search:results", msg.data);
            break;
        case "discover_search_results":
            bus("discover:search-results", msg.data);
            break;
        case "discover_data":
            bus("toast:log", { message: "Menerima data lagu! " + (msg.data.recent ? msg.data.recent.length : 0) + " items" });
            store.discover_recent = msg.data.recent || [];
            store.discover_favorites = msg.data.favorites || [];
            store.discover_cached   = msg.data.cached_tracks || [];
            store.discover_featured_artists = msg.data.featured_artists || [];
            store.discover_featured_genres = msg.data.featured_genres || [];
            store.discover_for_you = msg.data.for_you || [];
            store.discover_unheard = msg.data.unheard || [];
            store.discover_genre_affinity_genre = msg.data.genre_affinity_genre || null;
            store.discover_genre_affinity_artists = msg.data.genre_affinity_artists || [];
            store.discover_taste_spectrum = msg.data.taste_spectrum || [];
            bus("discover:tab-changed");
            bus("discover:recent-changed");
            bus("discover:personalization-changed");
            break;
        case "artist_detail":
            bus("discover:artist-detail", msg.data);
            break;
    }
}
