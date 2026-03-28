import "dotenv/config";
import OpenAI from "openai";

async function main() {
  const client = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
  });

  const resp = await client.responses.create({
    model: "gpt-4.1-mini",
    input: "한 문장으로 인사해, 한국어로.",
  });

  console.log(
    resp.output[0].content[0].text
  );
}

main().catch((err) => {
  console.error("ERROR:", err?.message || err);
  process.exit(1);
});