(function () {
    const TOOLTIP_ATTR = "data-hover-tooltip";

    let tooltipEl = null;
    let activeAnchor = null;

    function ensureTooltipEl() {
        if (tooltipEl) return tooltipEl;

        tooltipEl = document.createElement("div");
        tooltipEl.id = "floating-hover-tooltip";
        tooltipEl.setAttribute("role", "tooltip");
        tooltipEl.className = [
            "pointer-events-none fixed z-[1200] max-w-72 rounded-md",
            "bg-gray-900 px-2 py-1.5 text-[11px] leading-tight text-white",
            "opacity-0 shadow-lg transition-opacity duration-75",
        ].join(" ");
        tooltipEl.style.left = "-9999px";
        tooltipEl.style.top = "-9999px";
        document.body.appendChild(tooltipEl);
        return tooltipEl;
    }

    function getTooltipText(el) {
        if (!el) return "";
        return el.getAttribute(TOOLTIP_ATTR) || "";
    }

    function positionTooltip(anchor) {
        if (!tooltipEl || !anchor) return;

        const gap = 10;
        const rect = anchor.getBoundingClientRect();
        const tipRect = tooltipEl.getBoundingClientRect();

        let left = rect.left + rect.width / 2 - tipRect.width / 2;
        let top = rect.top - tipRect.height - gap;

        const minLeft = 8;
        const maxLeft = window.innerWidth - tipRect.width - 8;
        left = Math.max(minLeft, Math.min(left, Math.max(minLeft, maxLeft)));

        if (top < 8) {
            top = rect.bottom + gap;
        }

        tooltipEl.style.left = `${left}px`;
        tooltipEl.style.top = `${top}px`;
    }

    function showTooltip(anchor) {
        const text = getTooltipText(anchor);
        if (!text) return;

        const el = ensureTooltipEl();
        el.textContent = text;
        el.style.opacity = "1";
        activeAnchor = anchor;
        positionTooltip(anchor);
    }

    function hideTooltip(anchor) {
        if (!tooltipEl) return;
        if (anchor && activeAnchor && anchor !== activeAnchor) return;

        tooltipEl.style.opacity = "0";
        tooltipEl.style.left = "-9999px";
        tooltipEl.style.top = "-9999px";
        activeAnchor = null;
    }

    function findAnchor(target) {
        if (!(target instanceof Element)) return null;
        return target.closest(`[${TOOLTIP_ATTR}]`);
    }

    document.addEventListener("mouseover", (event) => {
        const anchor = findAnchor(event.target);
        if (!anchor) {
            hideTooltip();
            return;
        }
        showTooltip(anchor);
    });

    document.addEventListener("mouseout", (event) => {
        const anchor = findAnchor(event.target);
        if (!anchor) return;

        const related = event.relatedTarget;
        if (related instanceof Element && anchor.contains(related)) return;
        hideTooltip(anchor);
    });

    document.addEventListener("focusin", (event) => {
        const anchor = findAnchor(event.target);
        if (!anchor) return;
        showTooltip(anchor);
    });

    document.addEventListener("focusout", (event) => {
        const anchor = findAnchor(event.target);
        if (!anchor) return;
        hideTooltip(anchor);
    });

    window.addEventListener("scroll", () => {
        if (activeAnchor) positionTooltip(activeAnchor);
    }, true);

    window.addEventListener("resize", () => {
        if (activeAnchor) positionTooltip(activeAnchor);
    });
})();
