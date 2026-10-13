$(document).ready(function () {
  function showError(message) {
    // text() is intentional: the error message can contain user-controlled
    // template/values content and must never be parsed as HTML.
    $("#render").html($("<div>").addClass("error").text(message));
  }

  function convert() {
    const whitespaces = $('input[name="whitespace"]').is(":checked") ? 1 : 0;
    const input_type = $('input[name="type"]:checked').val();

    $.post("/convert", {
      template: $("#template").val(),
      values: $("#values").val(),
      type: input_type,
      whitespaces: whitespaces,
    })
      .done(function (response) {
        // The server escapes the rendered output, so injecting the marked-up
        // result as HTML is safe.
        $("#render").html(
          response.rendered_output.replaceAll(
            "•",
            '<span class="whitespace">•</span>',
          ),
        );
      })
      .fail(function (xhr) {
        const message =
          (xhr.responseJSON && xhr.responseJSON.error) ||
          `Request failed (${xhr.status})`;
        showError(message);
      });
  }

  $("#clear").click(function () {
    $("#template").val("");
    $("#values").val("");
    $("#render").html("");
  });

  $("#convert").click(convert);

  // Ctrl/Cmd + Enter triggers a conversion from anywhere on the page.
  $(document).on("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      convert();
    }
  });
});
