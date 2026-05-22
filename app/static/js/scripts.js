const scanMessages = [
    "SCANNING SOCIAL PLATFORMS...",
    "CHECKING USERNAME SIGNALS...",
    "ANALYZING DIGITAL FOOTPRINT...",
    "BUILDING INTELLIGENCE VIEW..."
];

let scanIndex = 0;
const scanText = document.getElementById("scan-text");

if (scanText) {
    setInterval(() => {
        scanIndex = (scanIndex + 1) % scanMessages.length;
        scanText.textContent = scanMessages[scanIndex];
    }, 1800);
}

const btn = document.getElementById("search-btn");

if (btn) {
    btn.addEventListener("click", () => {
        btn.innerText = "SCANNING...";
        btn.style.boxShadow = "0 0 25px #6c63ff";
        btn.style.transform = "scale(1.05)";
    });
}