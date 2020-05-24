#!/usr/bin/env python3

import argparse
import csv
from datetime import datetime
from difflib import SequenceMatcher
from typing import List

import spotipy
from dotenv import load_dotenv


def dict_get(adict: dict, *keys: str):
    current = adict
    for key in keys:
        if current:
            current = current.get(key, None)
    return current


class SpotifyImportException(Exception):
    """Catch all exception for SpotifyImport."""
    pass


class SpotifyImport:
    PLAYLIST_ADD_TRACK_LIMIT = 100
    LIBRARY_ADD_TRAFCK_LIMIT = 50

    def __init__(self, username, destination, songs, playlist=None):
        self.username = username
        self.destination = destination
        self.songs = songs
        if destination == 'playlist':
            self.playlist = playlist if playlist else f'Imported Playlist on {datetime.now().isoformat()}'

        load_dotenv()
        token = spotipy.util.prompt_for_user_token(self.username, redirect_uri='http://localhost:8080/',
                                                   scope='playlist-modify-private user-library-modify')
        self.sp = spotipy.Spotify(auth=token)

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
            self.sp.user_playlist_add_tracks(self._get_user_id(), playlist['id'], tracks)
            print(f'Added {len(tracks)} tracks to playlist')

    def _save_tracks_to_library(self, tracks):
        tracks_list = self._divide_tracks_into_chunks(tracks)
        for tracks in tracks_list:
            self.sp.current_user_saved_tracks_add(tracks)
            print(f'Added {len(tracks)} tracks to library')

    def _save_tracks(self, tracks: List[str], failed_count: int):
        if self.destination == 'playlist':
            playlist = self.sp.user_playlist_create(user=self._get_user_id(), name=self.playlist, public=False)
            self.sp.user_playlist_add_tracks(self._get_user_id(), playlist['id'], tracks)
        else:
            self._save_tracks_to_library(tracks)
        print(f'Saved a total of {len(tracks)} tracks to {self.destination}, '
              f'failed to add {failed_count} songs (see failed.txt)')

    def _run_txt(self):
        with open(self.songs) as songs_file, open('failed.txt', 'w') as failed_file:
            tracks = []
            failed_count = 0

            for song in (line.strip() for line in songs_file):
                song = self.replace_bad_words(song)

                if not song:
                    continue

                result = self.sp.search(song, limit=1)
                track_items = dict_get(result, 'tracks', 'items')
                track_id = track_items[0].get('id') if track_items else None
                if track_id:
                    tracks.append(track_id)
                else:
                    failed_count += 1
                    print(f"Couldn't find anything for {song!r}: {result!r}")
                    print(song, file=failed_file)

                if len(tracks) == self.PLAYLIST_ADD_TRACK_LIMIT:
                    self._save_tracks(tracks, failed_count)
                    tracks = []

            if tracks:
                self._save_tracks(tracks, failed_count)

        print('Done!')

    def _run_csv(self):
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

                if len(tracks) == self.LIBRARY_ADD_TRAFCK_LIMIT:
                    self._save_tracks(tracks, failed_count)
                    tracks = []

            if tracks:
                self._save_tracks(tracks, failed_count)

            print('Done!')

    def run(self):
        if self.songs.endswith('.txt'):
            self._run_txt()
        elif self.songs.endswith('.csv'):
            self._run_csv()
        else:
            raise SpotifyImportException("songs file must be either .txt or .csv")


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
