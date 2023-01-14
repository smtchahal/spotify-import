#!/usr/bin/env python3

import argparse
import csv
from datetime import datetime
from difflib import SequenceMatcher
from typing import List, Optional

import spotipy
from dotenv import load_dotenv
from spotipy import SpotifyOAuth
from spotipy.exceptions import SpotifyException


def dict_get(adict: dict, *keys: str):
    current = adict
    for key in keys:
        if current:
            current = current.get(key, None)
    return current


class SpotifyImportException(Exception):
    """Catch all exception for SpotifyImport."""
    pass


def scoped(scopes: List[str]):
    return ' '.join(scopes)


class SpotifyImport:
    PLAYLIST_ADD_TRACK_LIMIT = 100
    LIBRARY_ADD_TRACK_LIMIT = 50

    def __init__(self, username, destination, songs, playlist=None):
        self.username = username
        self.destination = destination
        self.songs = songs
        if destination == 'playlist':
            self.playlist = playlist if playlist else f'Imported Playlist on {datetime.now().isoformat()}'

        load_dotenv()
        scope = scoped(['playlist-modify-private', 'user-library-modify'])
        # scope = scoped(['playlist-modify-private', 'user-library-modify', 'playlist-read-private'])
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, open_browser=False))

    def _get_user_id(self):
        return self.sp.me()['id']

    @staticmethod
    def _divide_tracks_into_chunks(tracks):
        per_request_track_threshold = 100
        track_sub_lists = [tracks[i:i + per_request_track_threshold] for i in
                           range(0, len(tracks), per_request_track_threshold)]
        return track_sub_lists

    @staticmethod
    def replace_bad_words(song: str):
        bad_words = ('feat. ', 'ft. ', ' (Original Mix)', ' (Original mix)', ' (original mix)', ' &')
        for word in bad_words:
            song = song.replace(word, '')
        return song

    def _save_tracks_to_playlist(self, playlist, tracks):
        tracks_list = self._divide_tracks_into_chunks(tracks)
        for tracks in tracks_list:
            self.sp.playlist_add_items(playlist['id'], tracks)
            print(f'Added {len(tracks)} tracks to playlist')

    def _save_tracks_to_library(self, tracks):
        tracks_list = self._divide_tracks_into_chunks(tracks)
        for tracks in tracks_list:
            self.sp.current_user_saved_tracks_add(tracks)
            print(f'Added {len(tracks)} tracks to library')

    def _save_tracks(self, tracks: List[str], failed_count: int, playlist: Optional[dict] = None):
        if self.destination == 'playlist':
            if playlist is None:
                playlist = self.sp.user_playlist_create(user=self._get_user_id(), name=self.playlist, public=False)
            self.sp.playlist_add_items(playlist['id'], tracks)
        else:
            self._save_tracks_to_library(tracks)
        print(f'Saved a total of {len(tracks)} tracks to {self.destination}, '
              f'failed to add {failed_count} songs (see failed.txt)')

    def _run_txt(self):
        playlist = self.sp.user_playlist_create(user=self._get_user_id(), name=self.playlist, public=False)

        with open(self.songs) as songs_file, open('failed.txt', 'w') as failed_file:
            tracks = []
            failed_count = 0

            for song in (line.strip() for line in songs_file):
                song = self.replace_bad_words(song)

                if not song:
                    continue

                try:
                    result = self.sp.search(song, limit=1)
                except SpotifyException as e:
                    failed_count += 1
                    print(f"Couldn't retrieve tracks for {song!r}: {e}")
                    print(song, file=failed_file)
                else:
                    track_items = dict_get(result, 'tracks', 'items')
                    track_id = track_items[0].get('id') if track_items else None
                    if track_id:
                        tracks.append(track_id)
                    else:
                        failed_count += 1
                        print(f"Couldn't find anything for {song!r}: {result!r}")
                        print(song, file=failed_file)

                    if len(tracks) == self.PLAYLIST_ADD_TRACK_LIMIT:
                        self._save_tracks(tracks, failed_count, playlist)
                        tracks = []

            if tracks:
                self._save_tracks(tracks, failed_count, playlist)

        print('Done!')

    def _run_csv(self):
        playlist = self.sp.user_playlist_create(user=self._get_user_id(), name=self.playlist, public=False)

        with open(self.songs) as songs_csv, open('failed.txt', 'w') as failed_file:
            tracks = []
            failed_count = 0

            required_fields = ('title', 'artist')
            datareader = csv.DictReader(songs_csv)
            if not all(field in datareader.fieldnames for field in required_fields):
                raise SpotifyImportException(
                    f"Some of the required fields {required_fields!r} missing from {self.songs!r}")
            for row in datareader:
                title = row['title']
                artist = row['artist']
                album = row.get('album', None)

                if album:
                    query = ' - '.join((artist, title, album))
                else:
                    query = ' - '.join((artist, title))
                query = self.replace_bad_words(query)
                result = self.sp.search(query)
                track_items = dict_get(result, 'tracks', 'items')
                if not track_items:
                    failed_count += 1
                    print(f"Failed {query!r}")
                    print(query, file=failed_file)
                    continue

                track_ids_and_names = [(item['id'], ' - '.join((', '.join(artist['name'] for artist in item['artists']),
                                                                item['name'],
                                                                item['album']['name'])))
                                       for item in track_items]
                track_ids_and_names.sort(key=lambda x: SequenceMatcher(None, query, x[1]).ratio(), reverse=True)
                track_id = track_ids_and_names[0][0]

                tracks.append(track_id)

                if len(tracks) == self.LIBRARY_ADD_TRACK_LIMIT:
                    self._save_tracks(tracks, failed_count, playlist)
                    tracks = []

            if tracks:
                self._save_tracks(tracks, failed_count, playlist)

            print('Done!')

    def _search_user_playlist_by_name(self, name_to_search):
        batch_size = 50
        offset = 0
        playlist = None
        while True:
            response = self.sp.current_user_playlists(limit=batch_size, offset=offset)
            if not response['next'] or not response['items']:
                break
            playlists = response['items']
            playlist = [p for p in playlists if p['name'] == name_to_search]
            playlist = playlist[0] if playlist else None
            offset += batch_size
        return playlist

    def run(self):
        if self.songs.endswith('.txt'):
            self._run_txt()
        elif self.songs.endswith('.csv'):
            self._run_csv()
        else:
            raise SpotifyImportException("songs file must be either .txt or .csv")

    def _experiment(self):
        def artistify(track):
            return ', '.join(artist['name'] for artist in track['artists'])

        def print_track(track):
            print(track['id'] + ' ' + artistify(track) + ' ' + track['name'])

        def print_tracks(tracks):
            for track in tracks:
                print_track(track)

        batch_size = 50
        print("Hello world")
        print(self._get_user_id())
        playlist = self._search_user_playlist_by_name('Playlist name here')
        offset = 0
        trigger_words = ['mixed', 'radio mix', 'radio edit', 'club edit', 'edit']
        # words = '(' + '|'.join(word.replace(' ', r'\s') for word in trigger_words) + ')'
        # pattern = re.compile(rf'(.*)(\s*[-(\s]\s*{words}\)?)', re.IGNORECASE)
        while True:
            response = self.sp.playlist_items(playlist['id'], fields='items(track(id,name,artists(id,name))),next',
                                              limit=batch_size, offset=offset)
            if not response['next']:
                break
            # pprint(response)
            tracks = [i['track'] for i in response['items']]
            for track in tracks:
                if any(word in track['name'].lower() for word in trigger_words):
                    artist_names = artistify(track)
                    print(artist_names + ' ' + track['name'])
                    # clean_name = pattern.sub(r'\1', track['name']).strip(' -')
                    clean_name = track['name']
                    for word in trigger_words:
                        clean_name = clean_name.lower().replace(word, '')
                    clean_name = clean_name.strip(' -')
                    search_term = artist_names + ' ' + clean_name
                    found_tracks = self.sp.search(search_term, limit=10, type='track')['tracks']['items']
                    i = 1
                    for ft in found_tracks:
                        print(f'''{i}. {artistify(ft)} {ft['name']}''')
                        i += 1

                    while True:
                        choices = input('Choose (e.g. 1,2,3): ')
                        try:
                            choices = [int(c) for c in choices.split(',')]
                            if any(c > i or c < 1 for c in choices):
                                raise ValueError
                        except ValueError:
                            print('Invalid choice, please select a number from the options above')
                            continue

                        selected_tracks = [t[1] for t in enumerate(found_tracks) if (t[0] + 1) in choices]
                        selected_track_ids = [t['id'] for t in selected_tracks]
                        print(selected_track_ids)
                        print_tracks(selected_tracks)
                        self._save_tracks_to_library(selected_track_ids)
                        self._save_tracks_to_playlist(playlist, selected_track_ids)
                        break

            offset += batch_size
        pass


def main():
    parser = argparse.ArgumentParser(
        description='Simple CLI utility to import songs into a Spotify library or playlist')
    parser.add_argument('username', help='your Spotify username')
    parser.add_argument('songs', help='path to your songs.txt or songs.csv file')

    subparsers = parser.add_subparsers(metavar='destination', dest='destination', required=True,
                                       help='where to save the songs, one of: library, playlist')
    subparsers.add_parser('library', help='in your Spotify library, or your "Liked Songs", or whatever Spotify is '
                                          'calling it these days')
    parser_dest = subparsers.add_parser('playlist', help='in a newly created playlist of the specified name')
    parser_dest.add_argument('playlist', help='playlist name', default=None)

    args = parser.parse_args()

    playlist = getattr(args, 'playlist', None)
    spotify_import = SpotifyImport(args.username, args.destination, args.songs, playlist)
    spotify_import.run()


if __name__ == '__main__':
    main()
