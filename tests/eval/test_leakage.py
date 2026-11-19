from eval.leakage import leakage_report, ngrams


def test_ngrams_are_word_sets():
    assert ngrams("Cut the first 3 seconds off", 4) == {
        ("cut", "the", "first", "3"),
        ("the", "first", "3", "seconds"),
        ("first", "3", "seconds", "off"),
    }
    assert ngrams("hi there", 4) == {("hi", "there")}


def test_planted_near_duplicate_is_flagged_and_unrelated_text_is_not():
    train = ["please remove the sound from this video thanks", "make it vertical 1080 by 1920"]
    r = leakage_report(
        train,
        ["please remove the sound from this video thanks", "convert this old AVI to an MP4"],
        threshold=0.8,
    )
    assert r["max_jaccard"] == 1.0 and len(r["pairs_over_threshold"]) == 1
    assert r["pairs_over_threshold"][0]["train"] == train[0]


def test_empty_inputs():
    assert leakage_report([], ["a b c d e"])["max_jaccard"] == 0.0
    assert leakage_report(["a b c d e"], [])["tests"] == 0


def test_exact_duplicates_ignore_case_punctuation_and_spacing():
    from eval.leakage import exact_duplicates

    test = [
        {"id": "a", "request": "Trim this to 0s through 2s."},
        {"id": "b", "request": "make it  square"},
        {"id": "c", "request": "something new entirely"},
    ]
    r = exact_duplicates(["trim this to 0s through 2s", "Make it square!"], test)
    assert r["exact_duplicates"] == 2 and r["duplicate_ids"] == ["a", "b"]
    assert r["dedup_ids"] == ["c"] and r["share"] == round(2 / 3, 4)
    assert exact_duplicates([], [])["exact_duplicates"] == 0
