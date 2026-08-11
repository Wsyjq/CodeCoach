import os
import time

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:18101")


def main() -> None:
    username = f"e2e_user_{int(time.time())}"
    display_name = "E2E 学生"
    password = "secret123"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script(
            """
            (() => {
              const nativeFetch = window.fetch.bind(window);
              window.__codeCoachLearningDelayMs = 0;
              window.fetch = (input, init) => {
                const url = typeof input === 'string' ? input : input.url;
                const isLearningRequest = [
                  '/api/stats/summary',
                  '/api/memories',
                  '/api/reviews/due'
                ].some((path) => url.includes(path));
                if (!isLearningRequest || window.__codeCoachLearningDelayMs <= 0) {
                  return nativeFetch(input, init);
                }
                return new Promise((resolve) => {
                  window.setTimeout(resolve, window.__codeCoachLearningDelayMs);
                }).then(() => nativeFetch(input, init));
              };
            })();
            """
        )
        page = context.new_page()
        failed_requests: list[str] = []
        page.on("requestfailed", lambda request: failed_requests.append(f"{request.method} {request.url} {request.failure}"))

        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("登录个人学习空间")).to_be_visible()
        expect(page.get_by_label("用户名")).to_be_visible()
        expect(page.get_by_label("密码")).to_be_visible()

        page.get_by_role("button", name="登录 CodeCoach").click()
        expect(page.get_by_role("alert")).to_have_text("请输入用户名。")

        page.get_by_role("button", name="注册").click()
        expect(page.get_by_role("alert")).to_have_count(0)
        expect(page.get_by_label("显示名称")).to_be_visible()

        page.get_by_label("用户名").fill("ab")
        page.get_by_label("密码").fill(password)
        page.get_by_role("button", name="注册并进入").click()
        expect(page.get_by_role("alert")).to_have_text("用户名需为 3-32 位字母、数字、下划线或短横线。")

        page.get_by_label("用户名").fill(username)
        page.get_by_label("显示名称").fill("名" * 41)
        page.get_by_role("button", name="注册并进入").click()
        expect(page.get_by_role("alert")).to_have_text("显示名称不能超过 40 位。")

        page.get_by_label("显示名称").fill(display_name)
        page.get_by_label("密码").fill("123")
        page.get_by_role("button", name="注册并进入").click()
        expect(page.get_by_role("alert")).to_have_text("密码至少 6 位。")

        page.get_by_label("密码").fill("x" * 129)
        page.get_by_role("button", name="注册并进入").click()
        expect(page.get_by_role("alert")).to_have_text("密码不能超过 128 位。")

        page.get_by_label("密码").fill(password)
        page.get_by_role("button", name="注册并进入").click()
        page.wait_for_load_state("networkidle")

        expect(page.get_by_text("CodeCoach Workbench")).to_be_visible(timeout=10_000)
        expect(page.get_by_text(display_name)).to_be_visible()
        expect(page.get_by_text("服务输入", exact=True)).to_be_visible()

        page.reload()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("CodeCoach Workbench")).to_be_visible(timeout=10_000)
        expect(page.get_by_text(display_name)).to_be_visible()

        page.get_by_role("button", name="问知识").click()
        page.get_by_label("你想问什么").fill("scanf 为什么要加 &？")
        page.get_by_role("button", name="开始分析").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("多轮辅导对话")).to_be_visible()
        expect(page.get_by_text("scanf 为什么要加 &？")).to_be_visible()
        expect(page.get_by_text("一句话结论")).to_be_visible(timeout=10_000)

        page.locator(".workspace-section-tabs button", has_text="服务输入").click()
        page.locator(".service-button", has_text="代码纠错").click()
        page.get_by_label("题目（可选）").fill("输入一个整数 n，输出 n。")
        page.get_by_label("C 代码").fill('int main(){ int n; scanf("%d", n); return 0; }')
        page.get_by_label("遇到的问题").fill("我这个代码为什么过不了？")
        page.get_by_role("button", name="开始分析").click()
        expect(page.get_by_text("scanf 输入错误").first).to_be_visible(timeout=10_000)

        page.locator(".workspace-section-tabs button", has_text="我的错题").click()
        expect(page.get_by_text("1 条记录")).to_be_visible(timeout=10_000)
        page.get_by_role("button", name="查看详情").first.click()
        expect(page.get_by_text("错题详情")).to_be_visible(timeout=10_000)
        review_status = page.locator(".memory-detail-block", has_text="复习状态")
        expect(review_status).to_contain_text("复习中")
        expect(review_status).not_to_contain_text("reviewing")

        page.get_by_role("button", name="切换账号").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("登录个人学习空间")).to_be_visible(timeout=10_000)

        page.get_by_role("button", name="注册").click()
        page.get_by_label("用户名").fill(username)
        page.get_by_label("显示名称").fill(display_name)
        page.get_by_label("密码").fill(password)
        page.get_by_role("button", name="注册并进入").click()
        expect(page.get_by_role("alert")).to_have_text("这个用户名已经被注册。", timeout=10_000)

        page.get_by_role("button", name="登录").click()
        expect(page.get_by_role("alert")).to_have_count(0)
        page.get_by_label("用户名").fill(username)
        page.get_by_label("密码").fill("wrong-password")
        page.get_by_role("button", name="登录 CodeCoach").click()
        expect(page.get_by_text("用户名或密码错误。")).to_be_visible(timeout=10_000)

        page.get_by_label("密码").fill(password)
        page.evaluate("window.__codeCoachLearningDelayMs = 1500")
        page.get_by_role("button", name="登录 CodeCoach").click()
        expect(page.get_by_text("CodeCoach Workbench")).to_be_visible(timeout=10_000)
        expect(page.get_by_text(display_name)).to_be_visible()
        expect(page.locator('[aria-label="错题加载中"]')).to_have_text("…")
        expect(page.locator('[aria-label="待复习加载中"]')).to_have_text("…")
        expect(page.locator('[aria-label="掌握度加载中"]')).to_have_text("…")

        expect(page.locator('[aria-label="错题加载中"]')).to_have_count(0, timeout=10_000)
        first_metric = page.locator(".overview-metrics > div").first
        expect(first_metric).to_contain_text("1")

        unexpected_failures = [item for item in failed_requests if "net::ERR_ABORTED" not in item]
        assert not unexpected_failures, "Unexpected failed browser requests: " + " | ".join(unexpected_failures)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
