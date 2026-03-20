const http = require("http");
const server = http.createServer((_, res) => {
  res.writeHead(200, {"Content-Type":"text/html"});
  res.end(`<html><body style="font-family:sans-serif;padding:40px;background:#0a0a0a;color:#fff">
    <h2 style="color:#6366f1">HumanEye Dashboard</h2>
    <p style="color:#888">Frontend placeholder — replace with Next.js app.</p>
    <p>Backend API docs: <a href="http://localhost:8000/docs" style="color:#818cf8">
      http://localhost:8000/docs</a></p>
  </body></html>`);
});
server.listen(3000, () => console.log("Dashboard placeholder :3000"));
