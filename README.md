# Spotify Import

A simple CLI utility to import songs from a text or CSV file into a playlist or
your Spotify library ("Liked Songs").

## Setup

```bash
pip install -r requirements.txt
cp .env.sample .env
vi .env # edit in your OAuth credentials here
```

## Usage

```
$ ./spotify_import.py -h

usage: spotify_import.py [-h] username songs destination ...

Simple CLI utility to import songs into a Spotify library or playlist

positional arguments:
  username     your Spotify username
  songs        path to your songs.txt or songs.csv file
  destination  where to save the songs, one of: library, playlist
    library    in your Spotify library, or your "Liked Songs", or whatever
               Spotify is calling it these days
    playlist   in a newly created playlist of the specified name

optional arguments:
  -h, --help   show this help message and exit

```
