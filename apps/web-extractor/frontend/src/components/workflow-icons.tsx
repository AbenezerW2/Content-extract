import type { SVGProps } from "react"

type WorkflowIconProps = Omit<SVGProps<SVGSVGElement>, "viewBox">

export function WebPageWorkflowIcon(props: WorkflowIconProps) {
  return (
    <svg viewBox="0 0 48 48" fill="none" aria-hidden="true" {...props}>
      <rect x="5" y="7" width="38" height="34" rx="7" fill="#EFF6FF" stroke="#2563EB" strokeWidth="2.5" />
      <path d="M6.5 15.5h35" stroke="#60A5FA" strokeWidth="2.5" />
      <circle cx="11" cy="11.5" r="1.5" fill="#2563EB" />
      <circle cx="16" cy="11.5" r="1.5" fill="#38BDF8" />
      <circle cx="24" cy="28" r="8.5" fill="white" stroke="#2563EB" strokeWidth="2" />
      <path d="M15.5 28h17M24 19.5c2.3 2.3 3.4 5.1 3.4 8.5S26.3 34.2 24 36.5c-2.3-2.3-3.4-5.1-3.4-8.5s1.1-6.2 3.4-8.5Z" stroke="#2563EB" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function WholeSiteWorkflowIcon(props: WorkflowIconProps) {
  return (
    <svg viewBox="0 0 48 48" fill="none" aria-hidden="true" {...props}>
      <path d="M24 17v8M14 33v-3a5 5 0 0 1 5-5h10a5 5 0 0 1 5 5v3" stroke="#0EA5E9" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="24" cy="12" r="8" fill="#DBEAFE" stroke="#2563EB" strokeWidth="2.3" />
      <path d="M16 12h16M24 4c2 2.2 3 4.9 3 8s-1 5.8-3 8c-2-2.2-3-4.9-3-8s1-5.8 3-8Z" stroke="#2563EB" strokeWidth="1.4" />
      <rect x="6" y="32" width="16" height="10" rx="4" fill="#EFF6FF" stroke="#2563EB" strokeWidth="2.2" />
      <rect x="26" y="32" width="16" height="10" rx="4" fill="#ECFEFF" stroke="#0891B2" strokeWidth="2.2" />
      <path d="M11 37h6M31 37h6" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

export function BookStackWorkflowIcon(props: WorkflowIconProps) {
  return (
    <svg viewBox="0 0 48 48" fill="none" aria-hidden="true" {...props}>
      <path d="m8 32 27-5 5 5-27 6-5-6Z" fill="#22C55E" stroke="#15803D" strokeWidth="2" strokeLinejoin="round" />
      <path d="m8 32 1 6 5 4 26-6v-4l-27 6-5-6Z" fill="#F8FAFC" stroke="#15803D" strokeWidth="2" strokeLinejoin="round" />
      <path d="m5 21 28-4 6 5-28 5-6-6Z" fill="#F43F5E" stroke="#BE123C" strokeWidth="2" strokeLinejoin="round" />
      <path d="m5 21 1 6 5 5 28-6v-4l-28 5-6-6Z" fill="#F8FAFC" stroke="#BE123C" strokeWidth="2" strokeLinejoin="round" />
      <path d="m11 9 25-3 6 5-25 4-6-6Z" fill="#8B5CF6" stroke="#5B21B6" strokeWidth="2" strokeLinejoin="round" />
      <path d="m11 9 1 7 5 4 25-5v-4l-25 4-6-6Z" fill="#F8FAFC" stroke="#5B21B6" strokeWidth="2" strokeLinejoin="round" />
      <path d="m31 29 4-.8v8.1l-2-1-2 2v-8.3Z" fill="#FACC15" stroke="#CA8A04" strokeWidth="1.3" />
    </svg>
  )
}

export function YouTubeWorkflowIcon(props: WorkflowIconProps) {
  return (
    <svg viewBox="0 0 48 48" fill="none" aria-hidden="true" {...props}>
      <rect x="4" y="10" width="40" height="28" rx="10" fill="#FF0000" />
      <path d="m21 18 11 6-11 6V18Z" fill="white" stroke="white" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M9 16c1.4-2.2 3.5-3 6.8-3h16.4c3.3 0 5.4.8 6.8 3" stroke="#FF6666" strokeWidth="1.5" strokeLinecap="round" opacity=".8" />
    </svg>
  )
}
