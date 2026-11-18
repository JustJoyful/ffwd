from training.taskgen.loader import load_tasks
from training.teacher.run import pilot_selection


def test_pilot_selection_is_fixed_stratified_and_at_most_20():
    tasks = load_tasks("train", purpose="teacher")
    a, b = pilot_selection(tasks), pilot_selection(tasks)
    assert (
        [t["id"] for t in a] == [t["id"] for t in b]
        and len(a) <= 20
        and {t["split"] for t in a} == {"train"}
    )
    singles = {
        t["families"][0] for t in a if len(t["families"]) == 1 and not t["flags"]["ambiguous"]
    }
    assert {f"F{k}" for k in range(1, 13)} <= singles  # every family, incl. F11
    assert any(t["flags"]["ambiguous"] for t in a) and any(t["flags"]["unsupported"] for t in a)
