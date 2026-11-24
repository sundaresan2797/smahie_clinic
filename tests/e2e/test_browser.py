"""End-to-end browser tests (Playwright). Run with:  pytest -m browser"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.browser

PAGES = [
    "/",
    "/about",
    "/doctor",
    "/services",
    "/services/back-and-spine-concerns",
    "/appointment",
    "/gallery",
    "/faq",
    "/contact",
    "/privacy",
    "/terms",
]


@pytest.mark.parametrize("path", PAGES)
def test_pages_load_without_js_errors(page: Page, live_server, console_errors, path):
    page.goto(live_server + path, wait_until="networkidle")
    expect(page.locator("h1")).to_be_visible(timeout=6000)
    page.wait_for_timeout(500)
    assert console_errors == []


def test_desktop_navigation_and_services_dropdown(page: Page, live_server):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(live_server + "/", wait_until="networkidle")
    nav = page.get_by_role("navigation", name="Main")
    expect(nav.get_by_role("link", name="About")).to_be_visible(timeout=6000)
    nav.get_by_role("button", name="Services").click()
    menu = page.locator(".services-menu")
    expect(menu).to_be_visible()
    expect(menu.locator(".services-menu__item")).to_have_count(6)
    menu.get_by_role("link", name=re.compile("Knee and Hip Concerns")).click()
    expect(page).to_have_url(re.compile(r"/services/knee-and-hip-concerns$"))
    expect(page.locator("h1")).to_contain_text("Knee and Hip Concerns")


def test_header_becomes_solid_on_scroll(page: Page, live_server):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(live_server + "/about", wait_until="networkidle")
    header = page.locator("[data-header]")
    expect(header).not_to_have_class(re.compile("is-scrolled"))
    page.mouse.wheel(0, 600)
    expect(header).to_have_class(re.compile("is-scrolled"))


def test_mobile_menu_opens_and_closes(page: Page, live_server):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(live_server + "/", wait_until="networkidle")
    page.get_by_role("button", name="Open menu").click()
    panel = page.locator("#mobileNav")
    expect(panel).to_be_visible()
    expect(panel.get_by_role("link", name=re.compile("Gallery"))).to_be_visible()
    # Focus moves into the dialog once it has opened (focus trap), then Esc closes it.
    expect(panel).to_be_focused()
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(page.get_by_role("button", name="Open menu")).to_be_focused()


@pytest.mark.parametrize("path", ["/", "/appointment", "/doctor", "/contact", "/services/joint-pain-evaluation"])
def test_no_horizontal_overflow_on_small_phones(page: Page, live_server, path):
    page.set_viewport_size({"width": 320, "height": 640})
    page.goto(live_server + path, wait_until="networkidle")
    width = page.evaluate("document.documentElement.scrollWidth")
    assert width <= 320, f"{path} overflows horizontally ({width}px)"


def test_skip_link_moves_focus_to_main(page: Page, live_server):
    page.goto(live_server + "/about", wait_until="networkidle")
    page.keyboard.press("Tab")
    skip = page.get_by_role("link", name="Skip to main content")
    expect(skip).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("main#main")).to_be_focused()


def test_appointment_form_client_validation(page: Page, live_server):
    page.goto(live_server + "/appointment", wait_until="networkidle")
    page.get_by_role("button", name="Send Appointment Request").click()
    expect(page.locator("#full_name-error")).to_contain_text("full name")
    expect(page.locator("#phone-error")).to_contain_text("mobile number")
    expect(page.locator("#consent-error")).to_contain_text("privacy notice")
    expect(page.locator("#full_name")).to_be_focused()
    page.fill("#phone", "12345")
    page.locator("#phone").blur()
    expect(page.locator("#phone-error")).to_contain_text("valid 10-digit Indian mobile")


def test_appointment_form_submits_successfully(page: Page, live_server):
    page.goto(live_server + "/appointment", wait_until="networkidle")
    page.fill("#full_name", "Lakshmi Narayanan")
    page.fill("#phone", "98400 12345")
    min_date = page.get_attribute("#preferred_date", "min")
    max_date = page.get_attribute("#preferred_date", "max")
    assert min_date and max_date
    page.fill("#preferred_date", max_date)
    page.locator(".session-option", has_text="Evening").click()
    page.select_option("#preferred_time", "17:30")
    page.fill("#message", "Right shoulder pain for two months.")
    page.locator("input[name=consent]").check()
    page.get_by_role("button", name="Send Appointment Request").click()
    success = page.locator("[data-form-success]")
    expect(success).to_be_visible(timeout=8000)
    expect(success).to_contain_text("contact you to confirm the availability")
    expect(success).to_be_focused()


def test_selecting_time_selects_its_session(page: Page, live_server):
    page.goto(live_server + "/appointment", wait_until="networkidle")
    page.select_option("#preferred_time", "11:00")
    expect(page.locator("input[name=preferred_session][value=morning]")).to_be_checked()


def test_anatomy_guide_tabs(page: Page, live_server):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(live_server + "/", wait_until="networkidle")
    tabs = page.get_by_role("tablist", name="Areas of the body")
    tabs.scroll_into_view_if_needed()
    knee = tabs.get_by_role("tab", name="Knee")
    knee.click()
    expect(knee).to_have_attribute("aria-selected", "true")
    panel = page.locator("#anat-panel-knee")
    expect(panel).to_be_visible()
    expect(panel).to_contain_text("climbing stairs")
    expect(page.locator('[data-anat-region="knee"]')).to_have_class(re.compile("is-active"))
    page.keyboard.press("ArrowRight")
    expect(tabs.get_by_role("tab", name="Ankle")).to_be_focused()
    expect(page.locator("#anat-panel-ankle")).to_be_visible()
    expect(panel).to_be_hidden()


def test_gallery_lightbox_keyboard(page: Page, live_server):
    page.goto(live_server + "/gallery", wait_until="networkidle")
    first = page.locator("[data-gallery-item]").first
    first.click()
    dialog = page.locator("#lightbox")
    expect(dialog).to_be_visible()
    counter = dialog.locator("[data-lightbox-counter]")
    expect(counter).to_have_text("1 / 6")
    page.keyboard.press("ArrowRight")
    expect(counter).to_have_text("2 / 6")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    expect(counter).to_have_text("6 / 6")
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(first).to_be_focused()


def test_faq_accordion(page: Page, live_server):
    page.goto(live_server + "/faq", wait_until="networkidle")
    question = page.get_by_role("button", name=re.compile("Is my appointment confirmed"))
    expect(question).to_have_attribute("aria-expanded", "false")
    question.click()
    expect(question).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_text("Your appointment is confirmed only when")).to_be_visible()


def test_copy_phone_number(page: Page, live_server, context):
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(live_server + "/contact", wait_until="networkidle")
    page.get_by_role("button", name="Copy number").first.click()
    expect(page.locator("[data-toast]")).to_contain_text("copied")


def test_back_to_top(page: Page, live_server):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(live_server + "/faq", wait_until="networkidle")
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    button = page.get_by_role("button", name="Back to top")
    expect(button).to_have_class(re.compile("is-visible"))
    button.click()
    for _ in range(50):
        if page.evaluate("window.scrollY") < 50:
            break
        page.wait_for_timeout(100)
    assert page.evaluate("window.scrollY") < 50


def test_reduced_motion_shows_all_content_immediately(browser, live_server):
    context = browser.new_context(reduced_motion="reduce", viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(live_server + "/", wait_until="domcontentloaded")
    assert "motion-ok" not in page.evaluate("document.documentElement.className")
    expect(page.locator(".loader")).to_be_hidden()
    expect(page.locator("#hero-title")).to_be_visible()
    hidden = page.evaluate(
        """() => [...document.querySelectorAll('[data-anim], [data-anim-child], [data-hero], [data-story-item]')]
              .filter(e => getComputedStyle(e).opacity === '0' || getComputedStyle(e).visibility === 'hidden').length"""
    )
    assert hidden == 0
    assert page.evaluate("document.documentElement.classList.contains('lenis')") is False
    context.close()


def test_animated_content_is_revealed_after_scrolling(page: Page, live_server):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(live_server + "/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    height = page.evaluate("document.documentElement.scrollHeight")
    for y in range(0, height, 500):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(60)
    page.wait_for_timeout(1500)
    hidden = page.evaluate(
        """() => [...document.querySelectorAll('[data-anim="up"], [data-anim="fade"], [data-anim-child]')]
              .filter(e => getComputedStyle(e).opacity === '0').map(e => e.className)"""
    )
    assert hidden == []


def test_works_without_javascript(browser, live_server):
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(live_server + "/")
    expect(page.locator("#hero-title")).to_be_visible()
    expect(page.locator("#anat-panel-ankle")).to_be_visible()
    page.goto(live_server + "/faq")
    expect(page.get_by_text("Your appointment is confirmed only when")).to_be_visible()
    context.close()
