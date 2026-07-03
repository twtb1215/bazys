const { runWorkflow } = require("../../workflows/runner");

function agent(input) {

  return runWorkflow("hello_workflow", input);

}

module.exports = { agent };

