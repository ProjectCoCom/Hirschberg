/**
 * React UI component 'Actionbutton'.
 *
 * Responsibilities:
 * Renders the 'Actionbutton' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import type { ButtonHTMLAttributes, ReactNode } from "react";

type ActionButtonVariant = "primary" | "accent" | "info" | "danger";
type ActionButtonSize = "compact" | "dense";

type ActionButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  children: ReactNode;
  variant?: ActionButtonVariant;
  size?: ActionButtonSize;
};

export const ActionButton = ({
  children,
  className,
  variant = "accent",
  size = "dense",
  type = "button",
  ...buttonProps
}: ActionButtonProps) => {
  const classes = [
    "action-button",
    `action-button--${variant}`,
    `action-button--${size}`,
    className,
  ]
    .filter((value) => Boolean(value))
    .join(" ");

  return (
    <button className={classes} type={type} {...buttonProps}>
      {children}
    </button>
  );
};
