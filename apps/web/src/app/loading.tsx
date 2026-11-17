export default function Loading() {
  return (
    <main className="loading-screen">
      <span className="wordmark">12:12</span>
      <p role="status" aria-live="polite">
        Loading match intelligence…
      </p>
    </main>
  );
}
