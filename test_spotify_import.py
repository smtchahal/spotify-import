from unittest.mock import MagicMock

import pytest
from spotipy.exceptions import SpotifyException

import spotify_import
from spotify_import import SpotifyImport, replace_bad_words, dict_get, scoped, divide_tracks_into_chunks


def test_replace_bad_words():
    pairs = (
        ('Rodeo - feat. Nas', 'Rodeo - Nas'),
        ('INDUSTRY BABY (feat. Jack Harlow)', 'INDUSTRY BABY (Jack Harlow)'),
        ('Wild Thoughts (feat. Rihanna & Bryson Tiller)', 'Wild Thoughts (Rihanna Bryson Tiller)'),
        ('Ray Ban Vision ft. Cyhi Da Prynce', 'Ray Ban Vision Cyhi Da Prynce'),
        ('Delta - Original Mix', 'Delta'),
        ('This Nation (Original Mix)', 'This Nation'),
    )
    for (bad, good) in pairs:
        assert replace_bad_words(bad) == good


def test_scoped():
    assert scoped(['first', 'second']) == 'first second'
    assert scoped(['third']) == 'third'
    assert scoped(['foo bar baz', 'another', 'foo', 'bar']) == 'foo bar baz another foo bar'


def test_dict_get():
    dict_1 = {'first': {'second': {'third': 'value'}}}
    assert dict_get(dict_1, 'first', 'second', 'third') == 'value'
    dict_2 = {'first': 'thing'}
    assert dict_get(dict_2, 'first') == 'thing'
    dict_3 = {
        'other': 'stuff',
        'maybe': ['a', 'list!'],
        'first': {
            'could be': 'more stuff',
            'second': {
                'irrelevant': 'value',
                'third': 'value',
            }
        }
    }
    assert dict_get(dict_3, 'first', 'second', 'third') == 'value'
    assert dict_get(dict_3, 'first', 'second', 'wrong') is None
    assert dict_get(dict_3, 'first', 'second', 'wrong', 'house') is None
    assert dict_get(dict_3, 'first', 'second', 'third', 'fourth') is None
    assert dict_get({}, 'first') is None
    assert dict_get({}) is None


def test_divide_tracks_into_chunks():
    tracks = list(range(200))
    assert divide_tracks_into_chunks(tracks) == [list(range(100)), list(range(100, 200))]
    tracks = list(range(199))
    assert divide_tracks_into_chunks(tracks) == [list(range(100)), list(range(100, 199))]
    tracks = list(range(99))
    assert divide_tracks_into_chunks(tracks) == [list(range(99))]
    tracks = list(range(299))
    assert divide_tracks_into_chunks(tracks) == [list(range(100)), list(range(100, 200)), list(range(200, 299))]



def _track(track_id, query='song'):
    return {'id': track_id, 'name': query, 'artists': [{'name': 'artist'}], 'album': {'name': 'album'}}


@pytest.fixture
def sp(monkeypatch, tmp_path):
    """A SpotifyImport-ready mocked Spotify client; runs in tmp_path so failed.txt doesn't pollute the repo."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(spotify_import, 'load_dotenv', lambda: None)
    monkeypatch.setattr(spotify_import, 'SpotifyOAuth', MagicMock())
    client = MagicMock()
    client.me.return_value = {'id': 'user-id'}
    client.user_playlist_create.return_value = {'id': 'playlist-id'}
    client.search.side_effect = lambda query, **kwargs: {'tracks': {'items': [_track(f'id-{query}', query)]}}
    monkeypatch.setattr(spotify_import.spotipy, 'Spotify', lambda **kwargs: client)
    return client


def _write_songs(tmp_path, ext, count):
    path = tmp_path / f'songs.{ext}'
    if ext == 'txt':
        path.write_text(''.join(f'artist - title {i}\n' for i in range(count)))
    else:
        path.write_text('title,artist\n' + ''.join(f'title {i},artist\n' for i in range(count)))
    return str(path)


@pytest.mark.parametrize('ext', ['txt', 'csv'])
def test_library_destination_does_not_need_playlist(sp, tmp_path, ext):
    songs = _write_songs(tmp_path, ext, 3)
    SpotifyImport('library', songs).run()
    sp.user_playlist_create.assert_not_called()
    sp.current_user_saved_tracks_add.assert_called_once()
    assert len(sp.current_user_saved_tracks_add.call_args[0][0]) == 3


@pytest.mark.parametrize('ext', ['txt', 'csv'])
def test_playlist_destination_creates_single_playlist(sp, tmp_path, ext):
    # More songs than any per-request limit, so tracks are saved in several chunks
    songs = _write_songs(tmp_path, ext, 120)
    SpotifyImport('playlist', songs, 'My Playlist').run()
    sp.user_playlist_create.assert_called_once_with(user='user-id', name='My Playlist', public=False)
    assert sp.playlist_add_items.call_count > 1
    assert all(call[0][0] == 'playlist-id' for call in sp.playlist_add_items.call_args_list)
    assert sum(len(call[0][1]) for call in sp.playlist_add_items.call_args_list) == 120


@pytest.mark.parametrize('ext', ['txt', 'csv'])
def test_search_error_is_logged_and_skipped(sp, tmp_path, ext):
    songs = _write_songs(tmp_path, ext, 2)
    sp.search.side_effect = [
        SpotifyException(400, -1, 'Query too long'),
        {'tracks': {'items': [_track('good')]}},
    ]
    SpotifyImport('library', songs).run()
    sp.current_user_saved_tracks_add.assert_called_once_with(['good'])
    assert len((tmp_path / 'failed.txt').read_text().splitlines()) == 1
