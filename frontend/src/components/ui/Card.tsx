import React from 'react'
import { cn } from '../../utils/cn'

export interface CardProps {
  children: React.ReactNode
  className?: string
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export interface CardHeaderProps {
  title: string
  subtitle?: string
  action?: React.ReactNode
  className?: string
}

export interface CardBodyProps {
  children: React.ReactNode
  className?: string
}

const paddingClasses = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
}

export const Card: React.FC<CardProps> = ({ children, className, padding = 'md' }) => (
  <div
    className={cn(
      'bg-white rounded-xl border border-gray-200 shadow-sm',
      paddingClasses[padding],
      className
    )}
  >
    {children}
  </div>
)

export const CardHeader: React.FC<CardHeaderProps> = ({ title, subtitle, action, className }) => (
  <div className={cn('flex items-start justify-between mb-4', className)}>
    <div>
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
    </div>
    {action && <div className="ml-4 shrink-0">{action}</div>}
  </div>
)

export const CardBody: React.FC<CardBodyProps> = ({ children, className }) => (
  <div className={cn('', className)}>{children}</div>
)

export const CardDivider: React.FC<{ className?: string }> = ({ className }) => (
  <hr className={cn('border-gray-100 my-4', className)} />
)