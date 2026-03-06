"""Tests for golden_diff.py.

Uses fixture PDFs (fixture_v1.pdf, fixture_v2.pdf) that differ on page 2 only.
External tool calls (gs, montage, diff-pdf, git) are mocked where needed.

Run:
    uv run pytest tests/ac-editing-acroforms/ -v
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the module under test
import golden_diff
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
V1_PDF = FIXTURES / "fixture_v1.pdf"
V2_PDF = FIXTURES / "fixture_v2.pdf"


@pytest.fixture(autouse=True)
def _check_fixtures():
    """Ensure fixture PDFs exist."""
    assert V1_PDF.exists(), f"Missing fixture: {V1_PDF}. Run: uv run fixtures/create_test_pdfs.py"
    assert V2_PDF.exists(), f"Missing fixture: {V2_PDF}. Run: uv run fixtures/create_test_pdfs.py"


# ---------------------------------------------------------------------------
# find_changed_pdfs
# ---------------------------------------------------------------------------


class TestFindChangedPdfs:
    def test_returns_paths_from_git_diff(self, tmp_path: Path):
        fake_output = "src/test/resources/a.pdf\nsrc/test/resources/b.pdf\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
            result = golden_diff.find_changed_pdfs("origin/master", cwd=tmp_path)

        assert result == ["src/test/resources/a.pdf", "src/test/resources/b.pdf"]
        mock_run.assert_called_once()

    def test_empty_on_git_failure(self, tmp_path: Path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            result = golden_diff.find_changed_pdfs("origin/master", cwd=tmp_path)

        assert result == []

    def test_filter_glob(self, tmp_path: Path):
        fake_output = "src/test/resources/fr_broker.pdf\nsrc/test/resources/nl_direct.pdf\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
            result = golden_diff.find_changed_pdfs("origin/master", filter_glob="fr_*", cwd=tmp_path)

        assert result == ["src/test/resources/fr_broker.pdf"]

    def test_filter_no_match(self, tmp_path: Path):
        fake_output = "src/test/resources/nl_direct.pdf\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
            result = golden_diff.find_changed_pdfs("origin/master", filter_glob="fr_*", cwd=tmp_path)

        assert result == []


class TestResolveBaseRef:
    def test_prefers_explicit_base_ref(self, tmp_path: Path):
        assert golden_diff.resolve_base_ref("origin/main", cwd=tmp_path) == "origin/main"

    def test_uses_upstream_when_available(self, tmp_path: Path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="origin/feature-branch\n")

            result = golden_diff.resolve_base_ref(None, cwd=tmp_path)

        assert result == "origin/feature-branch"

    def test_falls_back_to_previous_commit_without_upstream(self, tmp_path: Path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")

            result = golden_diff.resolve_base_ref(None, cwd=tmp_path)

        assert result == "HEAD^"


# ---------------------------------------------------------------------------
# extract_master_pdf
# ---------------------------------------------------------------------------


class TestExtractMasterPdf:
    def test_success(self, tmp_path: Path):
        pdf_bytes = V1_PDF.read_bytes()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=pdf_bytes)
            dest = tmp_path / "out.pdf"
            ok = golden_diff.extract_master_pdf("origin/master", "some/path.pdf", dest)

        assert ok is True
        assert dest.exists()
        assert dest.read_bytes() == pdf_bytes

    def test_failure(self, tmp_path: Path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout=b"")
            dest = tmp_path / "out.pdf"
            ok = golden_diff.extract_master_pdf("origin/master", "missing.pdf", dest)

        assert ok is False


# ---------------------------------------------------------------------------
# render_page (requires gs)
# ---------------------------------------------------------------------------


class TestRenderPage:
    @pytest.mark.skipif(not golden_diff._find_gs(), reason="GhostScript not installed")
    def test_renders_page(self, tmp_path: Path):
        out = tmp_path / "page.png"
        ok = golden_diff.render_page(V1_PDF, 1, out, dpi=72)
        assert ok is True
        assert out.exists()
        assert out.stat().st_size > 100

    @pytest.mark.skipif(not golden_diff._find_gs(), reason="GhostScript not installed")
    def test_renders_page2(self, tmp_path: Path):
        out = tmp_path / "page2.png"
        ok = golden_diff.render_page(V1_PDF, 2, out, dpi=72)
        assert ok is True
        assert out.exists()

    def test_missing_gs(self, tmp_path: Path):
        with patch.object(golden_diff, "_find_gs", return_value=None):
            ok = golden_diff.render_page(V1_PDF, 1, tmp_path / "out.png")
        assert ok is False


# ---------------------------------------------------------------------------
# pdf_page_count (requires gs)
# ---------------------------------------------------------------------------


class TestPdfPageCount:
    @pytest.mark.skipif(not golden_diff._find_gs(), reason="GhostScript not installed")
    def test_counts_pages(self):
        assert golden_diff.pdf_page_count(V1_PDF) == 2
        assert golden_diff.pdf_page_count(V2_PDF) == 2

    def test_fallback_without_gs(self, tmp_path: Path):
        with patch.object(golden_diff, "_find_gs", return_value=None):
            assert golden_diff.pdf_page_count(V1_PDF) == 1


# ---------------------------------------------------------------------------
# find_differing_pages (requires gs)
# ---------------------------------------------------------------------------


class TestFindDifferingPages:
    @pytest.mark.skipif(not golden_diff._find_gs(), reason="GhostScript not installed")
    def test_detects_page2_diff(self, tmp_path: Path):
        diff_pages = golden_diff.find_differing_pages(V1_PDF, V2_PDF, tmp_path)
        # Page 1 is identical ("Hello"), page 2 differs ("Version 1" vs "Version 2")
        assert 2 in diff_pages
        assert 1 not in diff_pages

    @pytest.mark.skipif(not golden_diff._find_gs(), reason="GhostScript not installed")
    def test_identical_pdfs(self, tmp_path: Path):
        diff_pages = golden_diff.find_differing_pages(V1_PDF, V1_PDF, tmp_path)
        assert diff_pages == []


# ---------------------------------------------------------------------------
# create_side_by_side (requires montage)
# ---------------------------------------------------------------------------


class TestCreateSideBySide:
    @pytest.mark.skipif(not golden_diff._find_gs(), reason="GhostScript not installed")
    @pytest.mark.skipif(not golden_diff.check_dependencies() == [], reason="Missing deps")
    def test_creates_montage(self, tmp_path: Path):
        mp = tmp_path / "master.png"
        bp = tmp_path / "branch.png"
        golden_diff.render_page(V1_PDF, 2, mp, dpi=72)
        golden_diff.render_page(V2_PDF, 2, bp, dpi=72)

        sbs = tmp_path / "sbs.png"
        ok = golden_diff.create_side_by_side(mp, bp, sbs, page_num=2)
        assert ok is True
        assert sbs.exists()
        assert sbs.stat().st_size > 100


# ---------------------------------------------------------------------------
# create_overlay_diff (requires diff-pdf)
# ---------------------------------------------------------------------------


class TestCreateOverlayDiff:
    @pytest.mark.skipif(not golden_diff.check_dependencies() == [], reason="Missing deps")
    def test_creates_overlay(self, tmp_path: Path):
        out = tmp_path / "overlay.pdf"
        ok = golden_diff.create_overlay_diff(V1_PDF, V2_PDF, out)
        assert ok is True
        assert out.exists()

    @pytest.mark.skipif(not golden_diff.check_dependencies() == [], reason="Missing deps")
    def test_identical_files(self, tmp_path: Path):
        out = tmp_path / "overlay.pdf"
        # diff-pdf may or may not create output for identical files
        golden_diff.create_overlay_diff(V1_PDF, V1_PDF, out)
        # No assertion on result — behavior varies


# ---------------------------------------------------------------------------
# check_dependencies
# ---------------------------------------------------------------------------


class TestCheckDependencies:
    def test_reports_missing_tools(self):
        with (
            patch.object(golden_diff, "_find_gs", return_value=None),
            patch("shutil.which", return_value=None),
        ):
            missing = golden_diff.check_dependencies()
        assert "ghostscript" in missing
        assert "imagemagick" in missing
        assert "diff-pdf" in missing

    def test_all_present(self):
        with (
            patch.object(golden_diff, "_find_gs", return_value="/usr/bin/gs"),
            patch("shutil.which", return_value="/usr/bin/something"),
        ):
            missing = golden_diff.check_dependencies()
        assert missing == []
