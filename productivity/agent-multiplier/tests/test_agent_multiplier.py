import contextlib
import datetime as D
import io
import json
import os
import re
import tempfile
import unittest

from tests.fixtures import Claude, Codex, T0, at  # sets TZ=UTC and sys.path first

import measure as M  # noqa: E402
import agent_multiplier as CLI  # noqa: E402
import session_timeline as ST  # noqa: E402
import draft_config as DC  # noqa: E402

DAY = T0.date()
CFG = M.load_config(None)


def minutes(h):
    return round(h * 60, 2)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "projects")

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name="s1"):
        return os.path.join(self.root, "-home-dev-work-client-a-api", name + ".jsonl")

    def load(self, builder, name="s1", **kw):
        return M.load_claude_file(builder.write(self.path(name)), **kw)

    def compute(self, convs, cfg=CFG, **kw):
        return M.compute(convs, cfg, days=28, today=DAY, **kw)


class InputClassification(Base):
    def test_typed_queued_and_suggestions_are_yours(self):
        for src in ("typed", "queued", "suggestion_accepted"):
            self.assertEqual(M.classify_claude_user({"promptSource": src, "message": {"content": "x"}}), "yours")

    def test_system_peer_and_scheduled_are_not_yours(self):
        for src, origin in (("system", "task-notification"), ("system", "peer"), ("system", None), ("sdk", None)):
            o = {"promptSource": src, "origin": {"kind": origin}, "message": {"content": "x"}}
            self.assertEqual(M.classify_claude_user(o), "other")

    def test_compaction_and_meta_are_not_yours(self):
        self.assertEqual(M.classify_claude_user({"isCompactSummary": True, "message": {"content": "x"}}), "compaction")
        self.assertEqual(M.classify_claude_user({"isMeta": True, "message": {"content": "x"}}), "other")

    def test_legacy_records_without_prompt_source(self):
        self.assertEqual(M.classify_claude_user({"message": {"content": "add a test"}}), "yours")
        for text in ("<bash-stdout>ok</bash-stdout>", "<task-notification>..", "[Request interrupted by user]"):
            self.assertEqual(M.classify_claude_user({"message": {"content": text}}), "other")
        self.assertEqual(M.classify_claude_user({"origin": {"kind": "peer"}, "message": {"content": "hi"}}), "other")

    def test_approvals_answers_and_auto_accepts(self):
        c = (Claude().prompt(0).tool(1, "t1").result(1.2, "t1", source="config")
             .tool(2, "t2").result(2.5, "t2", source="user_temporary")
             .tool(3, "q1", name="AskUserQuestion").result(4, "q1", source="config", text="option B")
             .system_prompt(5, "<task-notification><task-id>x</task-id></task-notification>")
             .system_prompt(6, "message from a teammate", origin_kind="peer"))
        conv = self.load(c)
        self.assertEqual([x.kind for x in conv.inputs], ["prompt", "approval", "answer"])
        self.assertEqual(conv.inputs[1].label, "Bash")
        self.assertEqual(conv.inputs[1].read_from, at(2))

    def test_noise_lines_are_skipped(self):
        conv = self.load(Claude().noise(0).prompt(1).noise(2).text(3))
        self.assertEqual(len(conv.inputs), 1)


class AttentionWindows(Base):
    def test_prompt_window_is_reading_plus_typing(self):
        x = M.Input(at(10), "prompt", read_from=at(9), chars=50)  # 60 s reading + 10 s typing
        a, b = x.window()
        self.assertEqual((at(10) - a).total_seconds(), 70)
        self.assertEqual((b - at(10)).total_seconds(), M.AFTER_INPUT.total_seconds())

    def test_reading_and_typing_are_capped(self):
        x = M.Input(at(60), "prompt", read_from=at(0), chars=100000)
        a, b = x.window()
        self.assertEqual(b - a, M.WINDOW_CAP)
        y = M.Input(at(60), "prompt", read_from=at(0), chars=0)
        self.assertEqual(at(60) - y.window()[0], M.READ_CAP)

    def test_approval_window(self):
        x = M.Input(at(10), "approval", read_from=at(9.9))
        self.assertAlmostEqual((at(10) - x.window()[0]).total_seconds(), 6, places=3)
        y = M.Input(at(10), "approval", read_from=at(5))
        self.assertEqual(at(10) - y.window()[0], M.APPROVAL_READ_CAP)

    def test_overlapping_windows_merge(self):
        iv = [M.Input(at(m), "prompt", read_from=None, chars=0).window() for m in (0, 0.5, 10)]
        merged = M.union(iv)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0], (at(0) - M.MIN_PROMPT_LEAD, at(0.5) + M.AFTER_INPUT))

    def test_total_attention_is_wall_clock_across_conversations(self):
        a = self.load(Claude().prompt(0, "x" * 0), "a")
        b = self.load(Claude().prompt(0.2, "x" * 0), "b")
        data = self.compute([a, b])
        expected = ((at(0.2) + M.AFTER_INPUT) - (at(0) - M.MIN_PROMPT_LEAD)).total_seconds() / 3600
        self.assertAlmostEqual(data["total"]["attention"], round(expected, 2), places=2)

    def test_fair_split_adds_up(self):
        w = {"A": [(at(0), at(10))], "B": [(at(5), at(15))]}
        s = M.fair_split(w)
        self.assertAlmostEqual(minutes(s["A"]), 7.5)
        self.assertAlmostEqual(minutes(s["B"]), 7.5)
        self.assertAlmostEqual(sum(s.values()), M.hours(M.union(w["A"] + w["B"])))


class AgentTime(Base):
    def agent_minutes(self, conv):
        return minutes(self.compute([conv])["total"]["agent"])

    def assertMinutes(self, conv, expected):
        # the report rounds hours to 2 decimals (0.6 min)
        self.assertAlmostEqual(self.agent_minutes(conv), expected, delta=0.35)

    def test_turn_counts_until_last_agent_record(self):
        conv = self.load(Claude().prompt(0).text(1).tool(2, "t1").result(3, "t1").text(4).prompt(20).text(21))
        self.assertMinutes(conv, 5)  # 0->4 and 20->21; waiting for you is not work

    def test_silent_step_is_capped(self):
        conv = self.load(Claude().prompt(0).tool(1, "t1").result(100, "t1"))
        self.assertMinutes(conv, 1 + M.STEP_CAP.total_seconds() / 60)

    def test_waiting_for_approval_is_not_agent_work(self):
        conv = self.load(Claude().prompt(0).tool(1, "t1").result(6, "t1", source="user_temporary").text(7))
        self.assertMinutes(conv, 2)

    def test_subagents_count_in_parallel(self):
        main = Claude().prompt(0).tool(1, "a1", name="Agent").result(11, "a1")
        path = main.write(self.path("s1"))
        sub = Claude(sidechain=True).system_prompt(1, "subagent task", origin_kind=None).text(6).text(11)
        sub.write(os.path.join(self.path("s1")[:-6], "subagents", "agent-abc.jsonl"))
        conv = M.load_claude_file(path)
        self.assertMinutes(conv, 11 + 10)

    def test_background_task_runs_until_its_notification(self):
        c = (Claude().prompt(0).tool(1, "bg1", background=True).result(1.1, "bg1", background_id="task9").text(1.5)
             .system_prompt(31, "<task-notification><task-id>task9</task-id><tool-use-id>bg1</tool-use-id><status>completed</status></task-notification>")
             .text(32))
        conv = self.load(c)
        workers = {w.worker for w in conv.work}
        self.assertIn("background:bg1", workers)
        # main: 0->1.5 and 31->32 = 2.5 min; background: 1.1->31 = 29.9 min
        self.assertMinutes(conv, 2.5 + 29.9)
        split = self.compute([conv])["total"]["agent_by_worker"]
        self.assertAlmostEqual(split["background"] * 60, 29.9, delta=0.35)

    def test_background_task_is_capped(self):
        c = (Claude().prompt(0).tool(1, "bg1", background=True).result(1, "bg1", background_id="t").text(1)
             .system_prompt(301, "<task-notification><tool-use-id>bg1</tool-use-id></task-notification>"))
        conv = self.load(c)
        self.assertMinutes(conv, 1 + M.BACKGROUND_CAP.total_seconds() / 60)

    def test_background_agents_are_not_counted_twice(self):
        c = (Claude().prompt(0).tool(1, "ag1", name="Agent", background=True).result(1, "ag1", background_id="t").text(1)
             .system_prompt(60, "<task-notification><tool-use-id>ag1</tool-use-id></task-notification>"))
        conv = self.load(c)
        self.assertNotIn("background:ag1", {w.worker for w in conv.work})

    def test_turn_follows_the_category_of_its_trigger(self):
        conv = self.load(Claude().prompt(10).text(20))
        data = self.compute([conv], meetings=[(at(5), at(15))])
        row = {r["category"]: r for r in data["rows"]}
        self.assertAlmostEqual(row[CFG["meeting"]["name"]]["agent"], round(10 / 60, 2))


class Discounts(Base):
    def prompts(self, conv):
        return [x.t for x in conv.inputs if x.kind == "prompt"]

    def test_low_memory_kill(self):
        c = (Claude().prompt(0).text(1)
             .system_prompt(5, "<task-notification>Task stopped because the system is running low on memory</task-notification>")
             .prompt(8, "continue"))
        conv = self.load(c)
        self.assertEqual(self.prompts(conv), [at(0)])
        self.assertEqual(conv.discounted[0][1], "memory")

    def test_network_error(self):
        conv = self.load(Claude().prompt(0).api_error(1).prompt(3, "retry"))
        self.assertEqual(self.prompts(conv), [at(0)])
        self.assertEqual(conv.discounted[0][1], "network")

    def test_non_network_api_error_is_kept(self):
        conv = self.load(Claude().prompt(0).api_error(1, "API Error: 400 invalid request").prompt(3))
        self.assertEqual(len(self.prompts(conv)), 2)

    def test_session_resume(self):
        conv = self.load(Claude().prompt(0).text(1).resume(60).prompt(61, "go on"))
        self.assertEqual(self.prompts(conv), [at(0)])
        self.assertEqual(conv.discounted[0][1], "restart")

    def test_start_of_a_new_session_is_not_a_resume(self):
        conv = self.load(Claude().resume(0).prompt(1).text(2))
        self.assertEqual(self.prompts(conv), [at(1)])

    def test_died_mid_tool_call(self):
        conv = self.load(Claude().prompt(0).tool(1, "t1").prompt(10, "you died"))
        self.assertEqual(self.prompts(conv), [at(0)])
        self.assertEqual(conv.discounted[0][1], "died")

    def test_quick_interrupt_is_not_a_death(self):
        conv = self.load(Claude().prompt(0).tool(1, "t1").prompt(1.5, "stop, do this instead"))
        self.assertEqual(len(self.prompts(conv)), 2)

    def test_one_cut_discounts_one_prompt(self):
        c = Claude().prompt(0).api_error(1).api_error(2).prompt(3).text(4).prompt(6)
        conv = self.load(c)
        self.assertEqual(self.prompts(conv), [at(0), at(6)])

    def test_cut_too_long_ago_is_not_a_restart(self):
        conv = self.load(Claude().prompt(0).api_error(1).prompt(1 + 13 * 60))
        self.assertEqual(len(self.prompts(conv)), 2)

    def test_compactions_are_not_yours(self):
        conv = self.load(Claude().prompt(0).text(1).compaction(2).text(3))
        self.assertEqual(len(conv.inputs), 1)
        self.assertEqual(conv.compactions, 1)

    def test_routine_sessions_are_excluded(self):
        self.assertIsNone(self.load(Claude().prompt(0, "[agent-multiplier-routine] refresh the page").text(1)))
        self.assertIsNone(self.load(Claude().prompt(0, "[my-marker] go").text(1), "s2", routine_marker="[my-marker]"))
        self.assertIsNotNone(self.load(Claude().prompt(0, "normal").text(1), "s3"))

    def test_headless_runs_are_excluded_by_default(self):
        c = Claude(entrypoint="sdk-cli").prompt(0, source="sdk").text(10)
        self.assertIsNone(self.load(c))
        conv = self.load(c, "s2", include_headless=True)
        self.assertEqual(conv.inputs, [])
        self.assertAlmostEqual(minutes(self.compute([conv])["total"]["agent"]), 10, delta=0.35)


class Categories(Base):
    cfg = M.load_config(None)
    cfg["categories"] = [{"name": "Client A", "match": ["/clients/client-a"]},
                         {"name": "Writing", "match": ["blog", "client-a-docs"]}]
    cfg["coordination"]["dir_suffix"] = "/work"

    def test_first_match_wins(self):
        self.assertEqual(M.category_of("/home/dev/clients/client-a/client-a-docs", self.cfg), "Client A")
        self.assertEqual(M.category_of("/home/dev/my-BLOG", self.cfg), "Writing")

    def test_windows_paths(self):
        self.assertEqual(M.category_of("C:\\Users\\dev\\Clients\\Client-A\\api", self.cfg), "Client A")

    def test_coordination_and_other(self):
        self.assertEqual(M.category_of("/home/dev/work", self.cfg), "Coordination")
        self.assertEqual(M.category_of("/home/dev/work/", self.cfg), "Coordination")
        self.assertEqual(M.category_of("/home/dev/work/unlisted-repo", self.cfg), "Other")
        self.assertEqual(M.category_of("", self.cfg), "Other")

    def test_rows_per_category(self):
        a = self.load(Claude(cwd="/home/dev/clients/client-a").prompt(0).text(20).tool(24, "t").result(25, "t", source="user_permanent"), "a")
        b = self.load(Claude(cwd="/home/dev/blog").prompt(0).text(1), "b")
        rows = {r["category"]: r for r in self.compute([a, b], cfg=self.cfg)["rows"]}
        self.assertEqual(set(rows), {"Client A", "Writing"})
        self.assertEqual(rows["Client A"]["inputs"], 2)
        self.assertEqual(rows["Client A"]["approval_share"], 0.5)
        self.assertEqual(rows["Client A"]["sittings"], 1)
        total = self.compute([a, b], cfg=self.cfg)["total"]["attention"]
        self.assertAlmostEqual(rows["Client A"]["attention"] + rows["Writing"]["attention"], total, places=1)


class Meetings(Base):
    def write_cal(self, items):
        p = os.path.join(self.tmp.name, "cal.json")
        with open(p, "w") as fh:
            json.dump({"items": items}, fh)
        return p

    def ev(self, start, end, **kw):
        e = {"start": {"dateTime": start}, "end": {"dateTime": end},
             "attendees": [{"self": True, "responseStatus": "accepted"}, {"email": "x@example.com"}]}
        e.update(kw)
        return e

    def test_only_real_meetings(self):
        items = [
            self.ev("2026-03-10T10:00:00Z", "2026-03-10T10:30:00Z"),                                   # kept
            self.ev("2026-03-10T11:00:00Z", "2026-03-10T11:30:00Z", transparency="transparent"),       # free
            self.ev("2026-03-10T12:00:00Z", "2026-03-10T12:30:00Z", status="cancelled"),
            self.ev("2026-03-10T13:00:00Z", "2026-03-10T13:30:00Z", attendees=[{"self": True}]),      # just you
            self.ev("2026-03-10T14:00:00Z", "2026-03-10T14:30:00Z",
                    attendees=[{"self": True, "responseStatus": "declined"}, {"email": "x@example.com"}]),
            self.ev("2026-03-10T15:00:00Z", "2026-03-10T19:00:00Z"),                                   # > 3 h
            {"start": {"date": "2026-03-10"}, "end": {"date": "2026-03-11"}, "attendees": [{}, {}]},   # all day
            self.ev("2026-03-10T16:00:00+01:00", "2026-03-10T17:00:00+01:00"),                         # offset, kept
        ]
        ms = M.meetings_from(self.write_cal(items))
        self.assertEqual(ms, [(D.datetime(2026, 3, 10, 10, 0), D.datetime(2026, 3, 10, 10, 30)),
                              (D.datetime(2026, 3, 10, 15, 0), D.datetime(2026, 3, 10, 16, 0))])

    def test_inputs_during_meetings_move_category(self):
        conv = self.load(Claude().prompt(0).text(1).prompt(70).text(71))  # 09:00 and 10:10
        ms = M.meetings_from(self.write_cal([self.ev("2026-03-10T10:00:00Z", "2026-03-10T10:30:00Z")]))
        rows = {r["category"]: r for r in self.compute([conv], meetings=ms)["rows"]}
        self.assertEqual(rows["Questions during meetings"]["inputs"], 1)
        self.assertEqual(rows["Other"]["inputs"], 1)


class RemoteWork(Base):
    def test_remote_adds_agent_hours_without_attention(self):
        p = os.path.join(self.tmp.name, "remote.jsonl")
        line = json.dumps(["Client A", "2026-03-10T01:00:00Z", "2026-03-10T03:00:00Z", "Routine · nightly"])
        with open(p, "w") as fh:
            fh.write(line + "\n" + line + "\n\n")
        remote = M.load_remote([p, p])
        self.assertEqual(len(remote), 1)
        data = self.compute([], remote=remote)
        row = data["rows"][0]
        self.assertEqual((row["category"], row["agent"], row["attention"], row["remote"]), ("Client A", 2.0, 0.0, 2.0))
        self.assertEqual(data["total"]["agent"], 2.0)
        self.assertIsNone(data["total"]["ratio"])


class CodexSessions(Base):
    def test_interactive_codex(self):
        c = (Codex().env(0.1).user(1).event(1.1, "task_started").item(2).item(3, "function_call_output")
             .event(4, "exec_approval_request").item(6, "function_call_output").item(7, "message").event(7.1, "task_complete"))
        conv = M.load_codex_file(c.write(os.path.join(self.tmp.name, "codex", "r.jsonl")))
        self.assertEqual([x.kind for x in conv.inputs], ["prompt", "approval"])
        self.assertEqual(conv.cwd, "/home/dev/side/tool")
        # 1->4 is work, 4->6 waits for you, 6->7.1 is work
        self.assertAlmostEqual(minutes(self.compute([conv])["total"]["agent"]), 3 + 1.1, delta=0.35)

    def test_codex_exec_is_headless(self):
        c = Codex(originator="codex_exec", source="exec").user(1).item(2)
        self.assertIsNone(M.load_codex_file(c.write(os.path.join(self.tmp.name, "codex", "e.jsonl"))))


class Outputs(Base):
    def test_html_is_self_contained_and_has_data(self):
        conv = self.load(Claude().prompt(0, "SECRET-PROMPT-TEXT").text(5))
        recs = {"Other": json.load(open(os.path.join(os.path.dirname(__file__), "..", "examples", "recommendations", "writing.json")))}
        data = self.compute([conv], recommendations=recs)
        out = os.path.join(self.tmp.name, "page.html")
        CLI.render_html(data, out)
        page = open(out, encoding="utf-8").read()
        self.assertNotIn(CLI.PAYLOAD_SLOT, page)
        self.assertNotIn("SECRET-PROMPT-TEXT", page)
        self.assertIsNone(re.search(r"(src|href)\s*=\s*[\"']https?:", page))
        self.assertIn("prefers-color-scheme: dark", page)

    def test_timeline_hides_text_by_default(self):
        p = Claude().prompt(0, "SECRET-PROMPT-TEXT").tool(1, "t1").result(2, "t1", source="user_temporary").text(3, "AGENT-REPLY").write(self.path())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ST.main([p])
        out = buf.getvalue()
        self.assertIn("YOU prompt (18 chars)", out)
        self.assertIn("YOU approval: Bash", out)
        self.assertNotIn("SECRET-PROMPT-TEXT", out)
        self.assertNotIn("AGENT-REPLY", out)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ST.main([p, "--show-text"])
        self.assertIn("SECRET-PROMPT-TEXT", buf.getvalue())

    def test_timeline_masks_secrets(self):
        self.assertEqual(ST.clean("key sk-abcdefghijklmnopqrstuvwxyz", 100), "key [hidden]")

    def test_owner_of_remote_urls(self):
        self.assertEqual(DC.owner_of("git@github.com:some-org/repo.git"), "some-org")
        self.assertEqual(DC.owner_of("https://github.com/someone/repo"), "someone")
        self.assertEqual(DC.owner_of("https://dev.azure.com/acme/Project/_git/repo"), "acme")
        self.assertEqual(DC.owner_of("git@bitbucket.org:team/repo.git"), "team")

    def test_daily_series_and_day_boundary(self):
        conv = self.load(Claude().prompt(-6 * 60, "late night").text(-6 * 60 + 10))  # 03:00 counts for the day before
        data = self.compute([conv])
        days = {d["date"]: d for d in data["daily"]}
        self.assertEqual(len(data["daily"]), 28)
        self.assertGreater(days[(DAY - D.timedelta(days=1)).isoformat()]["attention"], 0)
        self.assertEqual(days[DAY.isoformat()]["attention"], 0)


class ReviewFixes(Base):
    def test_decided_by_human(self):
        self.assertTrue(M.decided_by_human({"permissionDecision": {"source": "user_temporary"}}))
        self.assertTrue(M.decided_by_human({"permissionDecision": {"source": "user:once"}}))
        for rec in ({"permissionDecision": {"source": "config"}}, {"permissionDecision": {"source": None}},
                    {"permissionDecision": "accept"}, {}):
            self.assertFalse(M.decided_by_human(rec))

    def test_message_from_another_session_is_not_yours(self):
        text = "Another Claude session sent a message: please rebase"
        self.assertEqual(M.classify_claude_user({"message": {"content": text}}), "other")
        conv = self.load(Claude().prompt(0).text(1).bare(5, "rebase onto main please").text(6))
        self.assertEqual([x.t for x in conv.inputs], [at(0)])  # promptSource seen earlier: the bare record is not yours
        conv = self.load(Claude().prompt(0).text(1).bare(5, "<bash-input>git status</bash-input>")
                         .bare(6, "<command-name>/clear</command-name>"), "s2")
        self.assertEqual(len(conv.inputs), 3)  # shell and slash commands you type have no promptSource either

    def test_old_transcripts_without_prompt_source_still_count(self):
        conv = self.load(Claude().prompt(0, source=None).text(1).prompt(5, "next", source=None).text(6))
        self.assertEqual(len(conv.inputs), 2)

    def test_routine_marker_after_a_meta_record(self):
        c = Claude().meta(0).system_prompt(0.1, "<system-reminder>hook output</system-reminder>", origin_kind=None)
        self.assertIsNone(self.load(c.prompt(0.5, "[agent-multiplier-routine] refresh").text(1)))

    def test_codex_agents_md_is_context(self):
        c = Codex().agents_md(0.05).env(0.1).user(1).item(2).event(2.1, "task_complete")
        conv = M.load_codex_file(c.write(os.path.join(self.tmp.name, "codex", "a.jsonl")))
        self.assertEqual([x.t for x in conv.inputs], [at(1)])
        r = Codex().agents_md(0.05).user(1, "[agent-multiplier-routine] daily run").item(2)
        self.assertIsNone(M.load_codex_file(r.write(os.path.join(self.tmp.name, "codex", "b.jsonl"))))

    def test_capped_background_hours_are_reported(self):
        c = (Claude().prompt(0).tool(1, "bg1", background=True).result(1, "bg1", background_id="t").text(1)
             .system_prompt(301, "<task-notification><tool-use-id>bg1</tool-use-id></task-notification>")
             .tool(302, "bg2", background=True).result(302, "bg2", background_id="u").text(302)
             .system_prompt(312, "<task-notification><tool-use-id>bg2</tool-use-id></task-notification>"))
        split = self.compute([self.load(c)])["total"]["agent_by_worker"]
        self.assertEqual(split["background_capped_tasks"], 1)
        self.assertAlmostEqual(split["background_capped_h"], 2.0, places=2)
        self.assertAlmostEqual(split["background"], 2.0 + 10 / 60, places=2)
        self.assertEqual(split["background_cap_h"], 2.0)

    def test_compactions_count_only_inside_the_window(self):
        conv = self.load(Claude().compaction(-40 * 24 * 60).prompt(0).text(1).compaction(2).text(3))
        self.assertEqual(conv.compactions, 2)
        self.assertEqual(self.compute([conv])["discounts"]["compactions"], 1)

    def test_time_helpers(self):
        self.assertEqual(M.to_local_naive("2026-03-10T09:00:00.123456789Z"), D.datetime(2026, 3, 10, 9, 0, 0, 123456))
        self.assertEqual(M.to_local_naive("2026-03-10T10:00:00+01:00"), D.datetime(2026, 3, 10, 9, 0))
        self.assertEqual(M.work_date(D.datetime(2026, 3, 10, 3, 59)), D.date(2026, 3, 9))
        self.assertEqual(M.work_date(D.datetime(2026, 3, 10, 4, 0)), D.date(2026, 3, 10))
        self.assertEqual(M.union([(at(5), at(6)), (at(0), at(2)), (at(2), at(3)), (at(9), at(9))]),
                         [(at(0), at(3)), (at(5), at(6))])

    def test_payload_cannot_close_the_script_element(self):
        data = self.compute([])
        data["rows"] = [{"category": "</script><script>alert(1)</script>"}]
        out = os.path.join(self.tmp.name, "page.html")
        CLI.render_html(data, out)
        page = open(out, encoding="utf-8").read()
        self.assertNotIn("</script><script>alert", page)
        blob = page.split('id="am-payload">', 1)[1].split("</script>", 1)[0]
        self.assertEqual(json.loads(blob)["rows"][0]["category"], "</script><script>alert(1)</script>")
        self.assertIn("computed_at", json.loads(blob))

    def test_cli_creates_missing_output_folders(self):
        out = os.path.join(self.tmp.name, "fresh", "out")
        args = ["--claude-root", os.path.join(self.tmp.name, "none"), "--codex-root", os.path.join(self.tmp.name, "none"),
                "--config", os.path.join(self.tmp.name, "no-config.json"), "--recommendations", os.path.join(self.tmp.name, "none"),
                "--remote", os.path.join(self.tmp.name, "none", "*.jsonl"),
                "--html", os.path.join(out, "latest.html"), "--json", os.path.join(out, "latest.json"),
                "--evidence", os.path.join(out, "evidence.json")]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CLI.main(args), 0)
        for name in ("latest.html", "latest.json", "evidence.json"):
            self.assertTrue(os.path.exists(os.path.join(out, name)))


class AttentionProfileTest(unittest.TestCase):
    def tearDown(self):
        M.set_attention_profile(M.DEFAULT_ATTENTION)

    def test_generous_profile_widens_windows_and_restores(self):
        base = M.WINDOW_CAP
        M.set_attention_profile("generous")
        self.assertGreater(M.WINDOW_CAP, base)
        self.assertGreater(M.READ_CAP, M.ATTENTION_PROFILES["conservative"]["READ_CAP"])
        self.assertEqual(M.attention_profile, "generous")
        M.set_attention_profile("conservative")
        self.assertEqual(M.WINDOW_CAP, base)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            M.set_attention_profile("lavish")


if __name__ == "__main__":
    unittest.main()
