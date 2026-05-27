import type { Variants, Transition } from 'framer-motion';

export const spring: Transition = {
  type: 'spring',
  stiffness: 400,
  damping: 30,
};

export const springGentle: Transition = {
  type: 'spring',
  stiffness: 200,
  damping: 25,
};

export const springStiff: Transition = {
  type: 'spring',
  stiffness: 600,
  damping: 40,
};

export const easeSmooth: Transition = {
  type: 'tween',
  ease: [0.4, 0, 0.2, 1],
  duration: 0.4,
};

export const easeCinematic: Transition = {
  type: 'tween',
  ease: [0.25, 0.46, 0.45, 0.94],
  duration: 0.6,
};

// Page entrance animations
export const pageVariants: Variants = {
  initial: {
    opacity: 0,
    y: 12,
    scale: 0.99,
  },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      ...easeCinematic,
      staggerChildren: 0.06,
    },
  },
  exit: {
    opacity: 0,
    y: -8,
    scale: 1.005,
    transition: { duration: 0.25, ease: [0.4, 0, 1, 1] },
  },
};

// Card entrance
export const cardVariants: Variants = {
  initial: { opacity: 0, y: 16, scale: 0.97 },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: springGentle,
  },
};

// Stagger container
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.07,
      delayChildren: 0.1,
    },
  },
};

export const staggerContainerFast: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.05,
    },
  },
};

// Fade up
export const fadeUp: Variants = {
  initial: { opacity: 0, y: 20 },
  animate: {
    opacity: 1,
    y: 0,
    transition: easeSmooth,
  },
};

// Fade in
export const fadeIn: Variants = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: { duration: 0.4, ease: 'easeOut' },
  },
};

// Scale in
export const scaleIn: Variants = {
  initial: { opacity: 0, scale: 0.9 },
  animate: {
    opacity: 1,
    scale: 1,
    transition: springGentle,
  },
};

// Slide from left
export const slideLeft: Variants = {
  initial: { opacity: 0, x: -20 },
  animate: {
    opacity: 1,
    x: 0,
    transition: easeSmooth,
  },
};

// Slide from right
export const slideRight: Variants = {
  initial: { opacity: 0, x: 20 },
  animate: {
    opacity: 1,
    x: 0,
    transition: easeSmooth,
  },
};

// Hover scale
export const hoverScale = {
  scale: 1.02,
  transition: spring,
};

// Hover lift
export const hoverLift = {
  y: -2,
  scale: 1.01,
  transition: spring,
};

// Tap
export const tapScale = {
  scale: 0.97,
  transition: springStiff,
};
