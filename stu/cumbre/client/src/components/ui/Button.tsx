import { ButtonHTMLAttributes, ReactNode } from 'react';
import clsx from 'clsx';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  children: ReactNode;
}

export default function Button({ variant = 'primary', children, className, ...props }: ButtonProps) {
  return (
    <button className={clsx(
      'px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50',
      variant === 'primary' && 'bg-primary-600 text-white hover:bg-primary-700',
      variant === 'secondary' && 'bg-gray-200 text-gray-700 hover:bg-gray-300',
      variant === 'danger' && 'bg-red-500 text-white hover:bg-red-600',
      variant === 'ghost' && 'text-gray-600 hover:bg-gray-100',
      className
    )} {...props}>
      {children}
    </button>
  );
}
