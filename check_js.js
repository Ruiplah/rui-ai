const fs = require("fs");
const h = fs.readFileSync("D:/llama/webui/index.html", "utf8");
const m = h.match(/<script>([\s\S]*?)<\/script>/);
try {
  new Function(m[1]);
  const browserCount = (h.match(/name:"browser_/g) || []).length;
  console.log("JS OK");
  console.log("browser tools:", browserCount);
  console.log("stock_quote:", h.includes('name:"stock_quote"'));
  console.log("fund_info:", h.includes('name:"fund_info"'));
  console.log("save_memory local:", h.includes("save_memory 本地闭环"));
  console.log("deny quote fixed:", h.includes('error:"用户拒绝执行"'));
} catch (e) {
  console.log("JS ERR:", e.message);
}
