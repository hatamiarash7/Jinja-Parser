$(document).ready(function () {
  $("#clear").click(function () {
    $("#template").val("");
    $("#render").val("");
    $("#values").val("");
    $("#render").html("");
  });

  $("#convert").click(function () {
    let whitespaces = $('input[name="whitespace"]').is(":checked") ? 1 : 0;
    let dummy = $('input[name="dummy"]').is(":checked") ? 1 : 0;
    let input_type = $('input[name="type"]:checked').val();

    $.post("/convert", {
      template: $("#template").val(),
      values: $("#values").val(),
      type: input_type,
      whitespaces: whitespaces,
      dummy: dummy,
    }).done(function (response) {
      response = response.rendered_output.replaceAll(
        "•",
        '<span class="whitespace">•</span>',
      );
      $("#render").html(response);
    });
  });
});
