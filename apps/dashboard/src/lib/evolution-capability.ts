/** Evolver capability 可由部署显式关闭；本地默认启用。 */
export function isEvolutionEnabled(): boolean {
  return process.env.EVOLVER_ENABLED?.toLowerCase() !== "false";
}
