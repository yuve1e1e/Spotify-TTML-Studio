(function generateTTML() {
    if (!Spicetify?.Playbar?.Button || !Spicetify?.Player) {
        setTimeout(generateTTML, 500);
        return;
    }

    let busy = false;
    const icon = `<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M13 1l.7 1.8L15.5 3.5l-1.8.7L13 6l-.7-1.8-1.8-.7 1.8-.7L13 1zM2 3h7v1.5H2V3zm0 4h9v1.5H2V7zm0 4h6v1.5H2V11z"/></svg>`;

    const getLabel = (el) => {
        if (!el) return "";
        const descId = el.getAttribute("aria-describedby");
        const descText = descId ? document.getElementById(descId)?.textContent : "";
        return [
            el._tippy?.props?.content,
            el.getAttribute("data-tippy-content"),
            el.getAttribute("aria-label"),
            el.getAttribute("title"),
            descText,
            el.textContent
        ].filter(Boolean).join(" ");
    };

    const refreshSpicyLyrics = async () => {
        try {
            if (typeof window.SpicyLyrics?.ReloadLyrics === "function") await window.SpicyLyrics.ReloadLyrics();
            else if (typeof window.SpicyLyrics?.FetchLyrics === "function") await window.SpicyLyrics.FetchLyrics();
            else if (typeof window.SpicyLyrics?.ResetLyrics === "function") await window.SpicyLyrics.ResetLyrics();
        } catch (_) {}

        try {
            Spicetify.Player.dispatchEvent(new Event("songchange"));
        } catch (_) {}

        // If Spicy Lyrics is open, briefly trigger its view refresh if needed
        const page = document.querySelector("#SpicyLyricsPage, [class*='SpicyLyrics']");
        if (page) {
            const reloadBtn = Array.from(page.querySelectorAll("button, [role='button']"))
                .find(b => /reload|refetch|refresh/i.test(getLabel(b)));
            if (reloadBtn) reloadBtn.click();
        }
    };

    const autoApplyToSpicyLyrics = async (ttmlText, filename) => {
        if (!ttmlText) return false;

        let page = document.querySelector("#SpicyLyricsPage, [class*='SpicyLyrics']");
        if (!page) {
            const lyricsBtn = document.querySelector('button[data-testid="lyrics-button"]') ||
                Array.from(document.querySelectorAll("button, [role='button']")).find(
                    b => /lyrics/i.test(getLabel(b)) && !/Generate Word-Synced TTML/i.test(getLabel(b))
                );
            if (lyricsBtn) {
                lyricsBtn.click();
                await new Promise(r => setTimeout(r, 800));
                page = document.querySelector("#SpicyLyricsPage, [class*='SpicyLyrics']");
            }
        }

        if (!page) return false;

        // Trigger mouseenter so Tippy initializes tooltips on all Spicy Lyrics buttons
        const allBtns = Array.from(page.querySelectorAll("button, [role='button']"));
        allBtns.forEach(b => b.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true })));
        await new Promise(r => setTimeout(r, 150));

        let localBtn = allBtns.find(b => /local\s*lyrics|custom\s*lyrics|import\s*lyrics|load\s*lyrics|ttml/i.test(getLabel(b)));

        // Fallback: 3rd button in Spicy Lyrics' floating top-center pill toolbar (Local Lyrics icon)
        if (!localBtn) {
            const pillBar = Array.from(page.querySelectorAll("div")).find(d => {
                const kids = Array.from(d.children).filter(c => c.matches("button, [role='button']"));
                return kids.length >= 4 && kids.length <= 6;
            });
            if (pillBar) {
                const kids = Array.from(pillBar.children).filter(c => c.matches("button, [role='button']"));
                localBtn = kids[2];
            }
        }

        if (!localBtn) return false;

        const file = new File([ttmlText], filename || "lyrics.ttml", { type: "text/xml" });
        const feedInput = (inp) => {
            const dt = new DataTransfer();
            dt.items.add(file);
            inp.files = dt.files;
            inp.dispatchEvent(new Event("input", { bubbles: true }));
            inp.dispatchEvent(new Event("change", { bubbles: true }));
        };

        const origPicker = window.showOpenFilePicker;
        const origClick = HTMLInputElement.prototype.click;
        let injected = false;

        window.showOpenFilePicker = async () => {
            injected = true;
            return [{ kind: "file", name: file.name, getFile: async () => file }];
        };

        HTMLInputElement.prototype.click = function () {
            if (this.type === "file") {
                injected = true;
                feedInput(this);
                return;
            }
            return origClick.apply(this, arguments);
        };

        const observer = new MutationObserver((mutations) => {
            for (const m of mutations) {
                for (const node of m.addedNodes) {
                    if (!(node instanceof HTMLElement)) continue;
                    const inp = node.matches?.('input[type="file"]') ? node : node.querySelector?.('input[type="file"]');
                    if (inp && !injected) {
                        injected = true;
                        feedInput(inp);
                    }
                    // Support drag-and-drop modals if Spicy Lyrics opens one
                    const dropTarget = node.querySelector?.("[class*='drop'], [class*='upload'], [class*='file']") || node;
                    if (!injected && dropTarget) {
                        const dt = new DataTransfer();
                        dt.items.add(file);
                        dropTarget.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
                    }
                    const modalUploadBtn = Array.from(node.querySelectorAll?.("button, [role='button']") || [])
                        .find(b => /upload|select|import|choose|load\s*file/i.test(getLabel(b)));
                    if (modalUploadBtn && !injected) {
                        modalUploadBtn.click();
                    }
                }
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });
        localBtn.click();

        await new Promise(r => setTimeout(r, 1600));
        observer.disconnect();
        window.showOpenFilePicker = origPicker;
        HTMLInputElement.prototype.click = origClick;

        if (injected) {
            await new Promise(r => setTimeout(r, 400));
            await refreshSpicyLyrics();
        }
        return injected;
    };

    const trigger = async (hardMode) => {
        if (busy) {
            Spicetify.showNotification("TTML generation already running...", true);
            return;
        }
        const item = Spicetify.Player.data?.item;
        if (!item) {
            Spicetify.showNotification("Play a track first!", true);
            return;
        }
        const targetUri = item.uri;
        const artists = item.artists?.map(a => a.name).join(", ") || item.metadata?.artist_name || "";
        const title = artists ? `${artists} - ${item.name}` : item.name;
        const duration = (Spicetify.Player.getDuration() || 0) / 1000;

        busy = true;
        btn.active = true;
        Spicetify.showNotification(`${hardMode ? "[Hard Mode] " : ""}Generating TTML for ${title}...`);

        try {
            const res = await fetch("http://127.0.0.1:8765/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, duration, hard: hardMode })
            });
            if (!res.ok) throw new Error("Script exited with an error");
            const data = await res.json();

            if (Spicetify.Player.data?.item?.uri !== targetUri) {
                Spicetify.showNotification("TTML saved to Custom lyrics (skipped auto-apply because track changed).");
            } else {
                const applied = await autoApplyToSpicyLyrics(data.ttml, data.filename);
                Spicetify.showNotification(
                    applied
                        ? `Applied & refreshed TTML for ${item.name}!`
                        : `TTML saved to Custom lyrics! Load it in Spicy Lyrics.`
                );
            }
        } catch (err) {
            Spicetify.showNotification(`TTML failed: ${err.message}`, true);
        } finally {
            busy = false;
            btn.active = false;
        }
    };

    const btn = new Spicetify.Playbar.Button(
        "Generate Word-Synced TTML (Right-Click / Shift+Click = Hard Mode)",
        icon,
        (self, e) => trigger(Boolean(e?.shiftKey)),
        false,
        false
    );

    btn.element.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        trigger(true);
    });
})();
