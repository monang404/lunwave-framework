export default {
  test: {
    environment: "jsdom",
    setupFiles: ["tests/frontend/setup.js"],
    include: ["tests/frontend/**/*.test.js"],
  },
};
