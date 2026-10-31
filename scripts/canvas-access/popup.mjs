const button = document.getElementById("run"),
  output = document.getElementById("report");
button.addEventListener("click", async () => {
  button.disabled = true;
  output.textContent = "Checking…";
  try {
    output.textContent = JSON.stringify(
      await chrome.runtime.sendMessage({ kind: "run" }),
      null,
      2,
    );
  } catch {
    output.textContent =
      "Check interrupted. Run again explicitly; no automatic retry.";
  } finally {
    button.disabled = false;
  }
});
