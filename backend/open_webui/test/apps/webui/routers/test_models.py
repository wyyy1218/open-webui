from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user


class TestModels(AbstractPostgresTest):
    BASE_PATH = '/api/v1/models'

    def setup_class(cls):
        super().setup_class()
        from open_webui.models.models import Model

        cls.models = Model

    def test_models(self):
        with mock_webui_user(id='2'):
            response = self.fast_api_client.get(self.create_url('/list'))
        assert response.status_code == 200
        assert len(response.json()['items']) == 0

        with mock_webui_user(id='2'):
            response = self.fast_api_client.post(
                self.create_url('/create'),
                json={
                    'id': 'my-model',
                    'base_model_id': 'base-model-id',
                    'name': 'Hello World',
                    'meta': {
                        'profile_image_url': '/static/favicon.png',
                        'description': 'description',
                        'capabilities': None,
                        'model_config': {},
                    },
                    'params': {},
                    'access_grants': [],
                },
            )
        assert response.status_code == 200

        with mock_webui_user(id='2'):
            response = self.fast_api_client.get(self.create_url('/list'))
        assert response.status_code == 200
        assert len(response.json()['items']) == 1

        with mock_webui_user(id='2'):
            response = self.fast_api_client.get(self.create_url('/model', query_params={'id': 'my-model'}))
        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 'my-model'
        assert data['name'] == 'Hello World'

        with mock_webui_user(id='2'):
            response = self.fast_api_client.post(
                self.create_url('/model/delete'),
                json={'id': 'my-model'},
            )
        assert response.status_code == 200

        with mock_webui_user(id='2'):
            response = self.fast_api_client.get(self.create_url('/list'))
        assert response.status_code == 200
        assert len(response.json()['items']) == 0
