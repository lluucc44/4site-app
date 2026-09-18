import time
from playwright.sync_api import sync_playwright

APP_URL = "https://4site-app-mx.streamlit.app/"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        print(f"Visitando {APP_URL}")

        # domcontentloaded (no networkidle): Streamlit mantiene un websocket
        # abierto, así que la red nunca queda del todo "idle".
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(8)  # dar tiempo a que cargue la SPA / la pantalla de reposo

        # Si la app está dormida aparece el botón para reactivarla.
        wake = page.get_by_text("get this app back up", exact=False)
        if wake.count() > 0:
            print("La app estaba dormida. Despertándola...")
            wake.first.click()
            time.sleep(30)  # esperar a que arranque el contenedor
            print("Listo: la app fue despertada.")
        else:
            print("La app ya estaba despierta.")

        browser.close()


if __name__ == "__main__":
    main()
