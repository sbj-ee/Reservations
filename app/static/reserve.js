// Reservation time picker: a flatpickr calendar for the start time plus a duration
// dropdown. On submit, the hidden start_time/end_time fields are filled with UTC
// "YYYY-MM-DDTHH:MM" values, the same format the server already accepts.
//
// The form's data-booked attribute lists the widget's other bookings (UTC). They are
// used to dot booked days in the calendar and to warn about overlaps before submit.
// The server's overlap check is still the source of truth.
(function () {
  "use strict";

  var STEP_MINUTES = 15;

  function pad(n) { return String(n).padStart(2, "0"); }

  // A stored "YYYY-MM-DD HH:MM" (UTC) -> Date.
  function parseUtc(s) {
    if (!s) return null;
    var d = new Date(s.trim().replace(" ", "T") + "Z");
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtUtc(d) {
    return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate()) +
      "T" + pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes());
  }

  function sameDay(a, b) {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate();
  }

  var DATE_TIME = { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" };
  var TIME_ONLY = { hour: "numeric", minute: "2-digit" };

  function fmtRange(a, b) {
    return a.toLocaleString(undefined, DATE_TIME) + " – " +
      b.toLocaleString(undefined, sameDay(a, b) ? TIME_ONLY : DATE_TIME);
  }

  function durationLabel(mins) {
    var d = Math.floor(mins / 1440), h = Math.floor((mins % 1440) / 60), m = mins % 60;
    var parts = [];
    if (d) parts.push(d + (d === 1 ? " day" : " days"));
    if (h) parts.push(h + (h === 1 ? " hour" : " hours"));
    if (m) parts.push(m + " min");
    return parts.join(" ") || "0 min";
  }

  function overlaps(aStart, aEnd, bStart, bEnd) {
    // Half-open ranges, matching models._has_overlap: back-to-back is allowed.
    return aStart < bEnd && aEnd > bStart;
  }

  function initForm(form) {
    var startInput = form.querySelector(".js-start");
    var durSelect = form.querySelector(".js-duration");
    var preview = form.querySelector(".js-end-preview");
    var conflictBox = form.querySelector(".js-conflict");
    var startField = form.querySelector('input[name="start_time"]');
    var endField = form.querySelector('input[name="end_time"]');
    var submitBtn = form.querySelector('button[type="submit"]');

    var booked = [];
    try { booked = JSON.parse(form.dataset.booked || "[]"); } catch (e) { booked = []; }
    booked = booked.map(function (b) {
      return { start: parseUtc(b.start), end: parseUtc(b.end), user: b.user };
    }).filter(function (b) { return b.start && b.end; });

    // Editing: pre-select the existing start and duration. If the duration isn't one
    // of the presets, add it as an extra option so it's kept unless changed.
    var initialStart = parseUtc(form.dataset.start);
    var initialEnd = parseUtc(form.dataset.end);
    if (initialStart && initialEnd) {
      var mins = Math.round((initialEnd - initialStart) / 60000);
      var match = Array.prototype.find.call(durSelect.options, function (o) {
        return Number(o.value) === mins;
      });
      if (!match) {
        match = new Option("Current: " + durationLabel(mins), String(mins));
        durSelect.add(match, 0);
      }
      durSelect.value = String(mins);
    }

    var fp = window.flatpickr(startInput, {
      enableTime: true,
      minuteIncrement: STEP_MINUTES,
      altInput: true,
      altFormat: "D, M j, Y  h:i K",
      dateFormat: "Y-m-d H:i",
      defaultDate: initialStart || null,
      minDate: initialStart ? null : "today",
      onChange: update,
      onDayCreate: function (_dObj, _dStr, _fp, dayElem) {
        var dayStart = dayElem.dateObj;
        var dayEnd = new Date(dayStart.getFullYear(), dayStart.getMonth(), dayStart.getDate() + 1);
        if (booked.some(function (b) { return overlaps(dayStart, dayEnd, b.start, b.end); })) {
          dayElem.classList.add("has-booking");
          dayElem.title = "Has bookings";
        }
      }
    });

    function currentRange() {
      var start = fp.selectedDates[0];
      if (!start) return null;
      return { start: start, end: new Date(start.getTime() + Number(durSelect.value) * 60000) };
    }

    function update() {
      var range = currentRange();
      conflictBox.hidden = true;
      conflictBox.textContent = "";
      if (!range) {
        preview.textContent = "";
        if (submitBtn) submitBtn.disabled = false;
        return;
      }
      preview.textContent = "Ends " + range.end.toLocaleString(undefined, DATE_TIME);

      var clashes = booked.filter(function (b) {
        return overlaps(range.start, range.end, b.start, b.end);
      });
      if (clashes.length) {
        var heading = document.createElement("strong");
        heading.textContent = "Overlaps an existing booking:";
        var list = document.createElement("ul");
        clashes.forEach(function (b) {
          var li = document.createElement("li");
          li.textContent = fmtRange(b.start, b.end) + (b.user ? " (" + b.user + ")" : "");
          list.appendChild(li);
        });
        conflictBox.appendChild(heading);
        conflictBox.appendChild(list);
        conflictBox.hidden = false;
      }
      if (submitBtn) submitBtn.disabled = clashes.length > 0;
    }

    durSelect.addEventListener("change", update);

    form.addEventListener("submit", function (e) {
      var range = currentRange();
      if (!range) {
        e.preventDefault();
        fp.open();
        return;
      }
      startField.value = fmtUtc(range.start);
      endField.value = fmtUtc(range.end);
    });

    update();
  }

  function init() {
    if (typeof window.flatpickr !== "function") return;
    var tz = "";
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { /* ignore */ }
    document.querySelectorAll(".js-tz-name").forEach(function (el) {
      if (tz) el.textContent = " (" + tz + ")";
    });
    document.querySelectorAll("form.js-reserve-form").forEach(initForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
