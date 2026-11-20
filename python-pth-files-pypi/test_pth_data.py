from pth_data import exec_lines, kind, where

NSPKG = ("import sys, types, os;has_mfs = sys.version_info > (3, 5);p = os.path.join("
         "sys._getframe(1).f_locals['sitedir'], *('google',));importlib = has_mfs and __import__('importlib.util')")


def test_where_wheel_root_runs_everywhere():
    assert where("coverage.pth", True) == "every"
    assert where("aspose_slides-26.10.0.data/purelib/asposeslides.pth", True) == "every"
    assert where("x-1.0.data/platlib/x.pth", True) == "every"


def test_where_data_scheme_runs_on_windows_only():
    assert where("adauto-1.0.5.data/data/adauto_post_install.pth", True) == "windows"
    assert where("python_certifi_win32-1.6.1.data/data/lib/site-packages/init.pth", True) == "windows"
    assert where("python_certifi_win32-1.6.1.data/data/Lib/site-packages/init.pth", True) == "windows"


def test_where_never():
    assert where("numpy_router-0.1.1.data/data/site-packages/numpy_router.pth", True) == "never"
    assert where("tmp/build-env-0gc7l757/lib/python3.10/site-packages/x.pth", True) == "never"
    assert where("pfix/auto_activate.pth", True) == "never"
    assert where("coverage.pth", False) == "never"      # source distribution


def test_exec_lines_follow_site_rules():
    text = "# comment\n/some/path\nimport os\n  import sys\nimportlib\nimport\tfoo\n"
    assert exec_lines(text) == ["import os", "import\tfoo"]


def test_kind():
    assert kind(NSPKG) == "namespace"
    assert kind("import coverage; coverage.process_startup()") == "own"
