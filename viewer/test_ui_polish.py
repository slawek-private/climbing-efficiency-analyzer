"""Synthetic checks of the fixed timing rail and independently styled choices."""
import copy
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from viewer.test_ui_022 import loaded
from viewer.design import apply_theme


def test_review_does_not_hide_timers_or_show_other_pages(tmp_path, monkeypatch):
    app, w = loaded(tmp_path, monkeypatch)
    QTest.qWait(50)
    w.resize(1024, 768)
    w.show_frame(10)
    w.toggle_hand_timer('rest', 'left')
    for theme in ('light', 'dark'):
        apply_theme(w, theme)
        for page in (w.events_card, w.point_box, w.footwork_panel, w.clip_review):
            w.review_tabs.setCurrentWidget(page)
            w.refresh_live()
            app.processEvents()
            assert w.width() == 1024, str([(name,getattr(w,name).minimumSizeHint().width()) for name in ('analysis_panel','measure_page','library','compare_page','transport','position','session_bar','review_tabs','point_box','events_card','footwork_panel')])
            assert page.isVisible()
            w.measurement_scroll.verticalScrollBar().setValue(w.measurement_scroll.verticalScrollBar().maximum())
            assert w.review_tabs.tabBar().isVisible()
            assert w.review_tabs.tabBar().visibleRegion().boundingRect() == w.review_tabs.tabBar().rect()
            assert all(not other.isVisible() for other in
                       (w.events_card, w.point_box, w.footwork_panel, w.clip_review)
                       if other is not page)
            button = w.hand_timer_buttons['rest', 'left']
            assert button.isVisible() and 'Stop rest' in button.text()
            assert button.visibleRegion().boundingRect() == button.rect()
    w.show_frame(12)
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert not w.document()['open_events']
    assert w.document()['events'][-1]['kind'] == 'rest'
    w.close()


def test_focus_and_clip_choices_preserve_geometry_and_uncertainty(tmp_path, monkeypatch):
    app, w = loaded(tmp_path, monkeypatch)
    w.resize(1024, 768)
    w.review_tabs.setCurrentWidget(w.clip_review)
    app.processEvents()
    before = copy.deepcopy(w.document())
    button = w.clip_review.buttons['unknown']
    geometry = button.geometry()
    button.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert button.geometry() == geometry and button.isChecked()
    assert button.text().startswith('✓')
    assert w.clip_review.reason.isVisible()
    assert w.document()['events'][0]['clip_method'] == 'unknown'
    assert w.document()['events'][0]['clip_reason'] == ''
    w.clip_review.reason.setCurrentIndex(w.clip_review.reason.findData('hidden'))
    assert w.document()['events'][0]['clip_reason'] == 'hidden'
    assert w.document()['events'][0]['start'] == before['events'][0]['start']
    assert w.document()['source'] == before['source']
    assert all(not b.isChecked() for key, b in w.clip_review.buttons.items() if key != 'unknown')
    w.close()


def test_library_requires_a_selection_for_batch_actions(tmp_path, monkeypatch):
    app, w = loaded(tmp_path, monkeypatch)
    w.library.render()
    assert not w.library.buttons['selected'].isEnabled()
    assert not w.library.assign_button.isEnabled()
    w.library.table.selectRow(0)
    assert w.library.buttons['selected'].isEnabled()
    assert w.library.assign_button.isEnabled()
    w.library.table.clearSelection()
    assert not w.library.buttons['selected'].isEnabled()
    w.close()


def test_preview_confirmation_can_cancel_without_starting_work(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    app, w = loaded(tmp_path, monkeypatch)
    before = copy.deepcopy(w.document())
    questions = []
    def cancel(parent, title, text):
        questions.append(text)
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, 'question', cancel)
    w.prepare_preview()
    assert questions and 'estimated cache' in questions[0]
    assert 'Originals, frames and timestamps are unchanged' in questions[0]
    assert w.preview_worker is None and w.document() == before
    w.close()


def test_long_identity_labels_fit_without_losing_their_full_text(tmp_path, monkeypatch):
    app, w = loaded(tmp_path, monkeypatch)
    d = copy.deepcopy(w.document())
    d['climber'] = 'A very long fictional athlete name ' * 8
    d['route'] = 'A very long fictional route name ' * 8
    assert w.commit(d)
    w.project_button.setText('A very long fictional project name ' * 8)
    QTest.qWait(50)
    w.resize(1024, 768)
    app.processEvents()
    assert w.width() == 1024
    assert w.athlete_button.text().startswith(d['climber'])
    assert w.attempt_context.text() == d['route']
    assert w.image.height() >= 400
    w.close()
