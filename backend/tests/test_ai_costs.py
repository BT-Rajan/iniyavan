# What the AI costs: the tokens the providers billed on the college's keys, priced at the admin's rates, by plan, by kind and by person.
# People's own keys cost the college nothing and are shown apart; photos (vision) are priced at the Claude rate.
import datetime as dt
import main
from main import Session_, User, AIEgress, Program, hp

def people():
    with Session_() as s:
        col = Program(name="B.E.", pattern="semester"); s.add(col); s.flush()
        future = dt.datetime.utcnow() + dt.timedelta(days=20)
        lite = [User(name=f"Lite {i}", email=f"l{i}@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=col.id, semester=1) for i in range(10)]
        pro = User(name="Pro", email="pro@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=col.id, semester=1, pro_until=future)
        own = User(name="Own", email="own@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=col.id, semester=1, ai_key=main.seal("sk-own-000000000000"))
        s.add_all(lite + [pro, own]); s.flush()
        now = dt.datetime.utcnow(); add = lambda u, kind, t, own=False, ago=1: s.add(AIEgress(user_id=u.id, kind=kind, tokens=t, own=own, chars=100, at=now - dt.timedelta(days=ago)))
        for i, u in enumerate(lite): add(u, "search", 1000 * (i + 1))  # 1,000 … 10,000 tokens: one heavy Lite user
        add(pro, "search", 50_000); add(pro, "mcq", 30_000); add(pro, "vision", 20_000)
        add(own, "search", 99_000, own=True)  # their own key: not the college's cost
        add(lite[0], "search", 777_000, ago=60)  # outside a 30-day window
        s.commit(); return {u.email: u.id for u in lite + [pro, own]}

def test_costs_are_billed_tokens_at_the_admins_rates_by_plan_kind_and_person(env):
    people()
    r = env.c.get("/api/admin/costs", headers=env.admin).json()
    prov = {p["provider"]: p for p in r["providers"]}
    assert r["priced"] is False and r["total"]["cost"] == 0 and prov["deepseek"]["tokens"] == 55_000 + 80_000 and prov["claude"]["tokens"] == 20_000  # tokens even before prices
    assert r["total"]["own_tokens"] == 99_000
    assert env.c.put("/api/admin/costs/rates", headers=env.admin, json={"prices": {"deepseek": 100, "claude": 1000}, "currency": "₹"}).json() == {"prices": {"deepseek": 100.0, "openai": 0.0, "claude": 1000.0, "qwen": 0.0, "perplexity": 0.0}, "currency": "₹"}
    r = env.c.get("/api/admin/costs", headers=env.admin).json()
    # DeepSeek 135,000 tokens at ₹100 a million = ₹13.5; Claude 20,000 at ₹1000 = ₹20
    assert r["priced"] and r["total"]["cost"] == 33.5 and r["total"]["per_30_days"] == 33.5
    plans = {p["plan"]: p for p in r["plans"]}
    assert plans["lite"]["people"] == 10 and plans["lite"]["active"] == 10 and plans["lite"]["cost"] == 5.5
    assert plans["lite"]["per_active_30_days"] == {"avg": 0.55, "median": 0.6, "p90": 0.9, "max": 1.0}  # ₹0.10 … ₹1.00 a person
    assert plans["pro"]["cost"] == 28.0 and plans["pro"]["per_active_30_days"]["max"] == 28.0
    assert plans["own"]["cost"] == 0 and plans["own"]["people"] == 1  # their own key: nothing for the college
    kinds = {k["kind"]: k for k in r["kinds"]}
    assert {p["provider"]: p["cost"] for p in r["providers"]} == {"deepseek": 13.5, "claude": 20.0}
    assert kinds["vision"]["cost"] == 20.0 and kinds["search"]["cost"] == 10.5 and kinds["search"]["own_tokens"] == 99_000 and kinds["mcq"]["cost"] == 3.0
    assert r["top"][0]["name"] == "Pro" and r["top"][0]["cost"] == 28.0
    week = env.c.get("/api/admin/costs?days=7", headers=env.admin).json(); assert week["total"]["per_30_days"] == round(33.5 * 30 / 7, 4)  # scaled to 30 days
    old = env.c.get("/api/admin/costs?days=90", headers=env.admin).json(); assert old["total"]["tokens"] == 135_000 + 20_000 + 777_000

def test_the_report_downloads_and_is_for_admins_only(env):
    people(); env.c.put("/api/admin/costs/rates", headers=env.admin, json={"prices": {"deepseek": 100}})
    csv = env.c.get("/api/admin/costs?format=csv", headers=env.admin)
    assert csv.status_code == 200 and "Pro,pro@x.com,pro,3,80000,20000,0" in csv.text.replace("\r", "")
    assert env.c.get("/api/admin/costs", headers=env.fac).status_code == 403 and env.c.get("/api/admin/costs", headers=env.stu).status_code == 403
    assert env.c.put("/api/admin/costs/rates", headers=env.fac, json={"prices": {"deepseek": 1}}).status_code == 403
    assert env.c.put("/api/admin/costs/rates", headers=env.admin, json={"prices": {"deepseek": -1}}).status_code == 400
    assert env.c.put("/api/admin/costs/rates", headers=env.admin, json={"prices": {"gemini": 1}}).status_code == 400
    assert env.c.put("/api/admin/costs/rates", headers=env.admin, json={"currency": "rupees!"}).status_code == 400

def test_each_provider_is_priced_at_its_own_rate(env):
    ids = people()
    with Session_() as s:  # the college switched to ChatGPT for a while
        s.add(AIEgress(user_id=ids["l1@x.com"], kind="search", tokens=40_000, provider="openai", chars=10)); s.commit()
    env.c.put("/api/admin/costs/rates", headers=env.admin, json={"prices": {"deepseek": 100, "openai": 500}})
    r = env.c.get("/api/admin/costs", headers=env.admin).json()
    assert {p["provider"]: p["cost"] for p in r["providers"]} == {"deepseek": 13.5, "openai": 20.0, "claude": 0}
    csv = env.c.get("/api/admin/costs?format=csv", headers=env.admin).text
    assert csv.lstrip("\ufeff").startswith("Name,Email or username,Plan,Requests,DeepSeek tokens,ChatGPT tokens,Claude tokens,Own-key tokens,Cost (₹)")
