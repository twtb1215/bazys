const hello = require("./hello");

function runWorkflow(name) {
  if (name === "hello_workflow") {
    return hello();
  }
  return "unknown workflow";
}

module.exports = { runWorkflow };
