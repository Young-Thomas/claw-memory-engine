const { execSync } = require("child_process");
const path = require("path");

const PLUGIN_ID = "claw-memory-engine";
const CLAW_BIN = "claw";

function runClaw(args) {
  try {
    const result = execSync(`${CLAW_BIN} ${args}`, {
      encoding: "utf-8",
      timeout: 30000,
      stdio: ["pipe", "pipe", "pipe"],
    });
    return { success: true, output: result.trim() };
  } catch (err) {
    return { success: false, output: err.stderr || err.message };
  }
}

module.exports = {
  id: PLUGIN_ID,

  async activate(config) {
    const dataDir = config.dataDir || "~/.claw";
    const forgettingEnabled =
      config.forgettingEnabled !== undefined ? config.forgettingEnabled : true;

    if (config.feishuAppId && config.feishuAppSecret) {
      runClaw(`config --key feishu_app_id --value ${config.feishuAppId}`);
      runClaw(`config --key feishu_app_secret --value ${config.feishuAppSecret}`);
    }
    if (config.feishuChatId) {
      runClaw(`config --key feishu_chat_id --value ${config.feishuChatId}`);
    }

    return {
      status: "active",
      message: `Claw Memory Engine activated. Data dir: ${dataDir}, Forgetting: ${forgettingEnabled}`,
    };
  },

  async deactivate() {
    return { status: "inactive", message: "Claw Memory Engine deactivated" };
  },

  memory: {
    async store({ alias, command, description, tags, project }) {
      let cmd = `remember ${alias} "${command}"`;
      if (description) cmd += ` --desc "${description}"`;
      if (tags) cmd += ` --tags "${tags}"`;
      if (project) cmd += ` --project "${project}"`;
      return runClaw(cmd);
    },

    async recall({ query, project, limit }) {
      let cmd = `find "${query}"`;
      if (project) cmd += ` --project "${project}"`;
      if (limit) cmd += ` --limit ${limit}`;
      return runClaw(cmd);
    },

    async list({ project, limit, all }) {
      let cmd = "list";
      if (project) cmd += ` --project "${project}"`;
      if (limit) cmd += ` --limit ${limit}`;
      if (all) cmd += " --all";
      return runClaw(cmd);
    },

    async delete({ alias, project, force }) {
      let cmd = `delete ${alias}`;
      if (project) cmd += ` --project "${project}"`;
      if (force) cmd += " --force";
      return runClaw(cmd);
    },

    async show({ alias, project }) {
      let cmd = `show ${alias}`;
      if (project) cmd += ` --project "${project}"`;
      return runClaw(cmd);
    },

    async checkForgetting({ chatId }) {
      let cmd = "scheduler-check";
      if (chatId) cmd += ` --chat-id ${chatId}`;
      return runClaw(cmd);
    },
  },

  async handleToolCall(toolName, args) {
    const memoryMethods = this.memory;
    if (memoryMethods[toolName]) {
      return memoryMethods[toolName](args);
    }
    return { success: false, output: `Unknown tool: ${toolName}` };
  },
};
