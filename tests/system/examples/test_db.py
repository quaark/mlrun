from mlrun import get_run_db, run_local, NewTask

from tests.system.base import TestMLRunSystem
from tests.system.examples.base import TestMlRunExamples


@TestMLRunSystem.skip_test_env_not_configured
class TestDB(TestMlRunExamples):
    def test_db_commands(self):
        db = get_run_db().connect()

        # {{run.uid}} will be substituted with the run id, so output will be written to different directories per run
        output_path = str(self.results_path / '{{run.uid}}')
        task = (
            NewTask(name='demo', params={'p1': 5}, artifact_path=output_path)
            .with_secrets('file', self.artifacts_path / 'secrets.txt')
            .set_label('type', 'demo')
        )

        run_object = run_local(
            task, command='training.py', workdir=str(self.artifacts_path)
        )
        self._logger.debug('Finished running task', run_object=run_object.to_dict())

        run_uid = run_object.uid()

        runs = db.list_runs()
        assert len(runs) == 1

        self._verify_run_metadata(
            runs[0]['metadata'],
            uid=run_uid,
            name='demo',
            project='default',
            labels={
                'v3io_user': self._test_env['V3IO_USERNAME'],
                'kind': '',
                'owner': self._test_env['V3IO_USERNAME'],
                'framework': 'sklearn',
            },
        )
        self._verify_run_spec(
            runs[0]['spec'],
            parameters={'p1': 5, 'p2': 'a-string'},
            inputs={'infile.txt': str(self.artifacts_path / 'infile.txt'),},
            outputs=[],
            output_path=str(self.results_path / run_uid),
            secret_sources=[],
            data_stores=[],
        )

        artifacts = db.list_artifacts()
        assert len(artifacts) == 4
        for artifact_key in ['chart', 'html_result', 'model', 'mydf']:
            artifact_exists = False
            for artifact in artifacts:
                if artifact['key'] == artifact_key:
                    artifact_exists = True
                    break
            assert artifact_exists

        runtimes = db.list_runtimes()
        assert len(runtimes) == 4
        for runtime_kind in ['dask', 'job', 'spark', 'mpijob']:
            runtime_exists = False
            for runtime in runtimes:
                if runtime['kind'] == runtime_kind:
                    runtime_exists = True
                    break
            assert runtime_exists
