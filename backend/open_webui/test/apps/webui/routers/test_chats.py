"""Router tests: shared chats count, Created At ordering, batch revoke (incl. partial success)."""

from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user

from open_webui.models.chats import ChatImportForm, Chats


class TestChatsSharedDashboard(AbstractPostgresTest):
    BASE_PATH = '/api/v1/chats'

    USER_A = 'chats-user-a'
    USER_B = 'chats-user-b'

    def setup_class(cls):
        super().setup_class()
        cls.chats = Chats

    def _import_and_share(self, user_id: str, title: str, created_at: int, updated_at: int) -> str:
        imported = self.chats.import_chats(
            user_id,
            [
                ChatImportForm(
                    chat={'title': title, 'history': {'messages': {}}},
                    created_at=created_at,
                    updated_at=updated_at,
                )
            ],
        )
        cid = imported[0].id
        self.chats.insert_shared_chat_by_chat_id(cid)
        return cid

    def test_shared_count_returns_total_for_current_user(self):
        self._import_and_share(self.USER_A, 'OnlyShared', 1, 1)
        self.chats.import_chats(
            self.USER_A,
            [
                ChatImportForm(
                    chat={'title': 'NotShared', 'history': {'messages': {}}},
                    created_at=2,
                    updated_at=2,
                )
            ],
        )
        with mock_webui_user(id=self.USER_A):
            r = self.fast_api_client.get(self.create_url('/shared/count'))
        assert r.status_code == 200
        assert r.json() == {'total': 1}

    def test_shared_count_with_query_matches_title_filter(self):
        token = 'UNIQUE-QUERY-TOKEN-xyz'
        self._import_and_share(self.USER_A, f'Alpha-{token}-a', 1, 1)
        self._import_and_share(self.USER_A, f'Beta-{token}-b', 2, 2)
        self._import_and_share(self.USER_A, 'NoMatch', 3, 3)
        with mock_webui_user(id=self.USER_A):
            cnt = self.fast_api_client.get(self.create_url('/shared/count', {'query': token}))
            lst = self.fast_api_client.get(self.create_url('/shared', {'query': token}))
        assert cnt.status_code == 200
        assert lst.status_code == 200
        assert cnt.json()['total'] == 2
        assert len(lst.json()) == 2

    def test_shared_list_order_by_created_at_ascending(self):
        c_early = self._import_and_share(self.USER_A, 'sort-early', 100, 900)
        c_mid = self._import_and_share(self.USER_A, 'sort-mid', 200, 100)
        c_late = self._import_and_share(self.USER_A, 'sort-late', 300, 200)
        with mock_webui_user(id=self.USER_A):
            r = self.fast_api_client.get(
                self.create_url(
                    '/shared',
                    {'order_by': 'created_at', 'direction': 'asc'},
                )
            )
        assert r.status_code == 200
        ids = [row['id'] for row in r.json()]
        assert ids == [c_early, c_mid, c_late]

    def test_shared_list_order_by_created_at_descending(self):
        c_early = self._import_and_share(self.USER_A, 'd-early', 100, 900)
        c_mid = self._import_and_share(self.USER_A, 'd-mid', 200, 100)
        c_late = self._import_and_share(self.USER_A, 'd-late', 300, 200)
        with mock_webui_user(id=self.USER_A):
            r = self.fast_api_client.get(
                self.create_url(
                    '/shared',
                    {'order_by': 'created_at', 'direction': 'desc'},
                )
            )
        assert r.status_code == 200
        ids = [row['id'] for row in r.json()]
        assert ids == [c_late, c_mid, c_early]

    def test_batch_revoke_all_requested_succeed(self):
        a = self._import_and_share(self.USER_A, 'r1', 1, 1)
        b = self._import_and_share(self.USER_A, 'r2', 2, 2)
        with mock_webui_user(id=self.USER_A):
            r = self.fast_api_client.post(
                self.create_url('/shared/revoke'),
                json={'ids': [a, b]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body['requested'] == 2
        assert body['revoked'] == 2
        assert body['skipped'] == 0
        assert body['failed_ids'] == []
        with mock_webui_user(id=self.USER_A):
            cnt = self.fast_api_client.get(self.create_url('/shared/count'))
        assert cnt.json()['total'] == 0

    def test_batch_revoke_partial_success_mixed_valid_invalid_ids(self):
        good = self._import_and_share(self.USER_A, 'ok-revoke', 1, 1)
        self._import_and_share(self.USER_A, 'stay-shared', 2, 2)
        unshared = self.chats.import_chats(
            self.USER_A,
            [
                ChatImportForm(
                    chat={'title': 'never-shared', 'history': {'messages': {}}},
                    created_at=3,
                    updated_at=3,
                )
            ],
        )[0].id
        other = self._import_and_share(self.USER_B, 'other', 1, 1)
        fake = '00000000-0000-0000-0000-000000000099'
        with mock_webui_user(id=self.USER_A):
            r = self.fast_api_client.post(
                self.create_url('/shared/revoke'),
                json={'ids': [good, fake, unshared, other]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body['requested'] == 4
        assert body['revoked'] == 1
        assert body['skipped'] == 3
        assert body['failed_ids'] == []
        with mock_webui_user(id=self.USER_A):
            cnt = self.fast_api_client.get(self.create_url('/shared/count'))
        assert cnt.json()['total'] == 1

    def test_batch_revoke_empty_ids_returns_400(self):
        with mock_webui_user(id=self.USER_A):
            r = self.fast_api_client.post(
                self.create_url('/shared/revoke'),
                json={'ids': []},
            )
        assert r.status_code == 400

    def test_batch_revoke_duplicate_ids_are_deduped(self):
        cid = self._import_and_share(self.USER_A, 'dup', 1, 1)
        with mock_webui_user(id=self.USER_A):
            r = self.fast_api_client.post(
                self.create_url('/shared/revoke'),
                json={'ids': [cid, cid, cid]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body['requested'] == 1
        assert body['revoked'] == 1
        assert body['skipped'] == 0

    def test_shared_cross_page_revoke_updates_count_list_and_order_subsequence(self):
        """Day 8: 120 shared rows (two pages at limit 60), revoke 5 across pages, count/list/subsequence."""
        user = 'chats-user-day8'
        for i in range(120):
            t = i + 1
            self._import_and_share(user, f'day8-{i:04d}', created_at=t, updated_at=t)

        full_before = self.chats.get_shared_chat_list_by_user_id(
            user,
            filter=None,
            skip=0,
            limit=200,
        )
        ids_before = [row.id for row in full_before]
        assert len(ids_before) == 120

        with mock_webui_user(id=user):
            cnt0 = self.fast_api_client.get(self.create_url('/shared/count'))
            p1 = self.fast_api_client.get(self.create_url('/shared', {'page': 1}))
            p2 = self.fast_api_client.get(self.create_url('/shared', {'page': 2}))

        assert cnt0.status_code == 200
        assert cnt0.json()['total'] == 120
        assert p1.status_code == 200
        assert p2.status_code == 200
        page1_ids = [row['id'] for row in p1.json()]
        page2_ids = [row['id'] for row in p2.json()]
        assert len(page1_ids) == 60
        assert len(page2_ids) == 60
        assert page1_ids + page2_ids == ids_before

        to_revoke = [page1_ids[0], page1_ids[1], page2_ids[0], page2_ids[1], page2_ids[2]]
        assert len(set(to_revoke)) == 5

        with mock_webui_user(id=user):
            rev = self.fast_api_client.post(
                self.create_url('/shared/revoke'),
                json={'ids': to_revoke},
            )
            cnt1 = self.fast_api_client.get(self.create_url('/shared/count'))
            a1 = self.fast_api_client.get(self.create_url('/shared', {'page': 1}))
            a2 = self.fast_api_client.get(self.create_url('/shared', {'page': 2}))

        assert rev.status_code == 200
        body = rev.json()
        assert body['requested'] == 5
        assert body['revoked'] == 5
        assert body['skipped'] == 0
        assert body['failed_ids'] == []

        assert cnt1.json()['total'] == 115
        after_ids = [row['id'] for row in a1.json()] + [row['id'] for row in a2.json()]
        assert len(after_ids) == 115
        revoke_set = set(to_revoke)
        assert revoke_set.isdisjoint(after_ids)

        full_after = self.chats.get_shared_chat_list_by_user_id(
            user,
            filter=None,
            skip=0,
            limit=200,
        )
        ids_after = [row.id for row in full_after]
        assert ids_after == [x for x in ids_before if x not in revoke_set]
