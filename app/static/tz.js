// Reservation times are stored in UTC. This bridges the gap to the viewer's
// local time zone:
//   - display:  ".js-utc" elements (stored UTC) are rewritten to local time
//   - prefill:  "input.js-utc-input" values (stored UTC) become local for editing
//   - submit:   "input.js-local-dt" values (local) are converted to UTC before send
(function () {
  function pad(n) { return String(n).padStart(2, "0"); }

  // A stored "YYYY-MM-DD HH:MM" (UTC) -> Date.
  function parseUtc(s) {
    if (!s) return null;
    var iso = s.trim().replace(" ", "T");
    if (!/([zZ]|[+-]\d{2}:?\d{2})$/.test(iso)) iso += "Z";
    var d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }

  // A datetime-local value "YYYY-MM-DDTHH:MM" (local) -> Date.
  function parseLocal(s) {
    if (!s) return null;
    var d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtLocal(d, sep) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      sep + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function fmtUtc(d, sep) {
    return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate()) +
      sep + pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes());
  }

  function init() {
    document.querySelectorAll(".js-utc").forEach(function (el) {
      var d = parseUtc(el.getAttribute("datetime") || el.textContent);
      if (d) el.textContent = fmtLocal(d, " ");
    });

    document.querySelectorAll("input.js-utc-input").forEach(function (input) {
      var d = parseUtc(input.value);
      if (d) input.value = fmtLocal(d, "T");
    });

    document.querySelectorAll("form").forEach(function (form) {
      form.addEventListener("submit", function () {
        form.querySelectorAll("input.js-local-dt").forEach(function (input) {
          var d = parseLocal(input.value);
          if (d) input.value = fmtUtc(d, "T");
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
