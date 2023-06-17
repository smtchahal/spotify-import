from spotify_import import replace_bad_words, dict_get, scoped, divide_tracks_into_chunks


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

