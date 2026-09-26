import useBrowserNotifications, {
  NOTIFICATION_STATES,
} from "../../hooks/useBrowserNotifications.js";

const STATUS_LABELS = Object.freeze({
  [NOTIFICATION_STATES.NOT_ENABLED]: "NOT ENABLED",
  [NOTIFICATION_STATES.REQUESTING_PERMISSION]:
    "REQUESTING PERMISSION...",
  [NOTIFICATION_STATES.ENABLED]: "BROWSER ALERTS ENABLED",
  [NOTIFICATION_STATES.PERMISSION_DENIED]:
    "NOTIFICATION PERMISSION DENIED",
  [NOTIFICATION_STATES.UNAVAILABLE]:
    "BROWSER ALERTS UNAVAILABLE",
  [NOTIFICATION_STATES.REGISTRATION_FAILED]:
    "ALERT REGISTRATION FAILED",
});

export default function NotificationStatus() {
  const { status, enableAlerts } = useBrowserNotifications();

  const canEnable =
    status === NOTIFICATION_STATES.NOT_ENABLED ||
    status === NOTIFICATION_STATES.REGISTRATION_FAILED;

  const requesting =
    status === NOTIFICATION_STATES.REQUESTING_PERMISSION;

  return (
    <section className="border border-slate-700 bg-[#0a111a] px-4 py-4">
      <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">
            Notification status
          </p>
          <p className="mt-1 text-sm font-bold text-slate-100">
            {STATUS_LABELS[status]}
          </p>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-400">
            Browser alerts are optional. Permission is requested only when
            enabled by the operator.
          </p>
        </div>

        {canEnable ? (
          <button
            type="button"
            className="command-button"
            onClick={enableAlerts}
          >
            ENABLE BROWSER ALERTS
          </button>
        ) : null}

        {requesting ? (
          <button
            type="button"
            className="command-button"
            disabled
          >
            REQUESTING PERMISSION...
          </button>
        ) : null}
      </div>
    </section>
  );
}