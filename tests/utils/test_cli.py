from typer.testing import CliRunner

from panoptes.pocs.utils.cli.main import app

runner = CliRunner()


def test_app():
    """Tests the basic app"""
    result = runner.invoke(app, input='--help\n')
    assert 'pocs' in result.stdout
