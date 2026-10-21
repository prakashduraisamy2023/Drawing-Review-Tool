from backend.app.vision.page_renderer import PageRenderer


def test_page_renderer_caches_and_round_trips_pdf_coordinates(synthetic_drawing):
    with PageRenderer(synthetic_drawing, dpi=180) as renderer:
        first = renderer.render_page(1)
        render_time = renderer.render_time_ms
        second = renderer.render_page(1)
        pixel_box = first.pdf_to_pixel_bbox((36, 36, 120, 80))
        restored = first.pixel_to_pdf_bbox(pixel_box)

        assert first is second
        assert renderer.render_time_ms == render_time
        assert all(
            abs(actual - expected) < 0.5
            for actual, expected in zip(restored, (36, 36, 120, 80), strict=True)
        )
