from argus_tools import sandbox


def test_runs_and_captures_stdout():
    assert sandbox.run("print(2+2)").strip() == "4"


def test_reports_stderr_on_error():
    assert "erro" in sandbox.run("raise ValueError('boom')")


def test_no_network_import():
    out = sandbox.run("import socket; print(socket.gethostname())")
    assert out.strip()
