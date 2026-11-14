from removed_data import _covered, classify


def hit(module, context="module", kind="code"):
    return {"module": module, "path": "p.py", "line": 1, "context": context, "kind": kind}


def test_covered_by_backports():
    deps = ["legacy-cgi>=2.6", "standard-imghdr; python_version >= '3.13'", "audioop-lts",
            "setuptools", "zombie_imp", "standard-pipes; extra == 'cli'"]
    assert _covered(deps) == {"cgi", "cgitb", "imghdr", "audioop", "distutils", "imp"}


def test_worst_context_wins():
    c = {"project": "x", "hits": [hit("imp", "guarded"), hit("cgi", "function")]}
    assert classify(c)[0] == "function"
    c["hits"].append(hit("pipes", "module"))
    level, bad = classify(c)
    assert level == "module" and [h["module"] for h in bad] == ["pipes"]


def test_tests_and_setup_do_not_count():
    c = {"project": "x", "hits": [hit("distutils", kind="setup"), hit("imp", kind="test")]}
    assert classify(c)[0] == "other"


def test_guarded_only_is_safe():
    c = {"project": "x", "hits": [hit("imp", "guarded"), hit("pipes", "fallback"), hit("cgi", "gated")]}
    assert classify(c)[0] == "safe"


def test_declared_backport_removes_the_hit():
    c = {"project": "x", "requires_dist": ["audioop-lts; python_version >= '3.13'"],
         "hits": [hit("audioop")]}
    assert classify(c)[0] == "other"


def test_setuptools_provides_distutils():
    c = {"project": "setuptools", "hits": [hit("distutils")]}
    assert classify(c)[0] == "other"
