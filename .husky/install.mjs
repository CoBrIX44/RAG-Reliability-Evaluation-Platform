// Hosted builds may omit root devDependencies; skip before importing Husky.
if (
  process.env.VERCEL === "1" ||
  process.env.CI === "true" ||
  process.env.NODE_ENV === "production" ||
  process.env.HUSKY === "0"
) {
  process.exit(0);
}

const { default: husky } = await import("husky");
const message = husky();
if (message) console.log(message);
