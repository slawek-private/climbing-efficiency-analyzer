"""Smoke test for packaged builds: proves the bundle carries Qt, FFmpeg, the schema and ReportLab."""
import sys
import tempfile
from pathlib import Path


def run():
    import av, numpy as np
    from PySide6.QtWidgets import QApplication
    from .comparison import export_comparison
    from .labels import empty_labels, validate
    from .pdf_report import export_pdf
    from .simple import Window
    from .video import index_video, VideoReader
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder);video = folder/'check.mkv'
        with av.open(str(video), 'w') as out:
            stream = out.add_stream('ffv1', rate=10);stream.width = 32;stream.height = 32;stream.pix_fmt = 'yuv420p'
            for n in range(10):
                for packet in stream.encode(av.VideoFrame.from_ndarray(np.full((32, 32, 3), n*20, dtype=np.uint8), format='rgb24')):out.mux(packet)
            for packet in stream.encode():out.mux(packet)
        index = index_video(video);reader = VideoReader(video, index, 'auto');assert reader.frame(7).shape[:2] == (32, 32);reader.close()
        document = empty_labels(index['source']);validate(document)
        html = export_comparison([document], folder/'check.html');export_pdf(html, folder/'check.pdf')
        assert (folder/'check.pdf').read_bytes().startswith(b'%PDF')
        app = QApplication.instance() or QApplication(sys.argv);window = Window();window.saved = window.document();window.close()
        from PySide6.QtNetwork import QSslSocket
        assert QSslSocket.supportsSsl(), 'No TLS backend bundled: in-app updates could not reach GitHub'
        assert (Path(__file__).resolve().parent/'assets'/'icon.png').is_file(), 'App icon missing from bundle'
        from .projects import create, export_project, import_project
        project = create(folder/'data', 'Self-check');export_project(project, folder/'check.climbproject');assert import_project(folder/'other', folder/'check.climbproject').name == 'Self-check'
    print('Climb Studio self-check passed')
    return 0
