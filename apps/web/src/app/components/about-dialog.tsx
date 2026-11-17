"use client";
import { useEffect, useRef } from "react";
import { Icon } from "./icons";

export function AboutDialog({ close }: { close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className="forecast-dialog about-dialog"
      onClose={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close();
      }}
      aria-labelledby="about-title"
    >
      <div className="dialog-top">
        <span className="eyebrow">Built for the match</span>
        <button
          autoFocus
          className="icon-button"
          aria-label="Close model information"
          onClick={() => ref.current?.close()}
        >
          <Icon name="close" />
        </button>
      </div>
      <div className="dialog-body">
        <h2 id="about-title">A model. A point of view.</h2>
        <p>
          12:12 (twelve to twelve) estimates Valorant match outcomes using Elo
          ratings and real results from VLR.
        </p>
        <div className="model-facts">
          <div>
            <strong>1500</strong>
            <span>Starting rating</span>
          </div>
          <div>
            <strong>32</strong>
            <span>Elo K-factor</span>
          </div>
          <div>
            <strong>400</strong>
            <span>Rating scale</span>
          </div>
        </div>
        <h3>Read the board</h3>
        <p>
          Brighter probabilities identify a team with at least a 50% model probability.
          Close calls are matchups where neither team exceeds 60%; strong leans
          have a favorite at 70% or higher.
        </p>
        <h3>Keep the distinction</h3>
        <p>
          The board shows current research estimates. Saved forecasts are
          timestamped, immutable records made before a match. Historical
          availability is incomplete, so retrospective results are not
          leakage-certified performance.
        </p>
        <p className="detail-note">
          This is a forecasting tool. There are no trades, market prices, or
          order books. Live estimates use available scores; side, economy, and
          map-specific effects are not modeled.
        </p>
      </div>
    </dialog>
  );
}
