import { describe, expect, it } from "vitest";
import { parseAction } from "../src/actions";

const RUN =
  '{"action":"run","args":["-i","{in:clip}","{out:out1}"],"inputs":["clip"],"outputs":["out1"]}';

describe("parseAction (mirrors training/env/actions.py)", () => {
  it("parses plain JSON", () => expect(parseAction(RUN)).toMatchObject({ action: "run" }));
  it("strips think blocks and a json fence", () =>
    expect(parseAction("<think>\n</think>\n```json\n" + RUN + "\n```")).toMatchObject({
      action: "run",
    }));
  it("rejects trailing prose", () =>
    expect(parseAction(RUN + " this trims")).toHaveProperty("error"));
  it("rejects non-objects and unknown actions", () => {
    expect(parseAction("[1]")).toHaveProperty("error");
    expect(parseAction('{"action":"shell"}')).toHaveProperty("error");
  });
  it("rejects a run whose args are not a string list", () =>
    expect(
      parseAction('{"action":"run","args":"-i x","inputs":[],"outputs":["o"]}'),
    ).toHaveProperty("error"));
});
