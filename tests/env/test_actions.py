from training.env.actions import ParseError, parse_action

RUN = '{"action": "run", "args": ["-i", "{in:clip}", "{out:out1}"], "inputs": ["clip"], "outputs": ["out1"]}'


def test_parses_plain_json():
    assert parse_action(RUN)["action"] == "run"


def test_strips_empty_think_and_fence():
    assert parse_action(f"<think>\n\n</think>\n```json\n{RUN}\n```")["action"] == "run"
    assert parse_action(f"<think>I should trim.</think>{RUN}")["action"] == "run"


def test_trailing_prose_is_error():
    assert isinstance(parse_action(RUN + "\nThis trims the clip."), ParseError)


def test_two_objects_is_error():
    assert isinstance(parse_action(RUN + RUN), ParseError)


def test_schema_invalid_is_error():
    r = parse_action('{"action": "run", "args": "-i x", "inputs": [], "outputs": ["o"]}')
    assert isinstance(r, ParseError) and "args" in r.message


def test_not_json_is_error():
    assert isinstance(
        parse_action("Sure! Here is the command: ffmpeg -i in.mp4 out.mp4"), ParseError
    )
    assert isinstance(parse_action("[1, 2]"), ParseError)
