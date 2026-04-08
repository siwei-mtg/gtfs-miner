# Atomic Design Reference — React + Tailwind 组件架构

本文件定义了 Atomic Design 在 React + Tailwind 项目中的实践方法。当你不确定一个组件应该放在哪一层、或者如何设计组件接口时，参考此文件。

## Table of Contents

1. [层级判断决策树](#层级判断决策树)
2. [Atoms — 基础原子](#atoms--基础原子)
3. [Molecules — 分子组合](#molecules--分子组合)
4. [Organisms — 有机体](#organisms--有机体)
5. [Templates — 布局模板](#templates--布局模板)
6. [Pages — 页面实例](#pages--页面实例)
7. [Variant 模式](#variant-模式)
8. [组件接口设计规范](#组件接口设计规范)
9. [常见陷阱](#常见陷阱)

---

## 层级判断决策树

当你不确定一个组件应该放在哪一层时，按以下问题依次判断：

```
Q1: 这个组件是否只包含单一 HTML 元素或最基础的 UI 单元？
  → YES → Atom（如 Button, Input, Badge, Avatar, Icon wrapper）

Q2: 这个组件是否由 2-3 个 atoms 组合而成，完成一个小型但完整的功能？
  → YES → Molecule（如 SearchBar = Input + Button, StatCard = Icon + Number + Label）

Q3: 这个组件是否是一个独立的 UI 区块，可以单独放在页面的某个位置？
  → YES → Organism（如 Header, Sidebar, DataTable, PricingSection）

Q4: 这个组件是否只定义布局结构，不包含具体内容？
  → YES → Template（如 DashboardLayout, TwoColumnLayout）

Q5: 这个组件是否是一个完整的路由页面，含具体数据？
  → YES → Page
```

---

## Atoms — 基础原子

Atoms 是最小的可复用 UI 单元。它们不依赖任何其他自定义组件。

### Button

```jsx
import { cn } from '@/lib/utils';

const variants = {
  primary: 'bg-[var(--color-primary-500)] text-white hover:bg-[var(--color-primary-600)] shadow-sm hover:shadow-md active:scale-[0.98]',
  secondary: 'bg-[var(--color-gray-100)] text-[var(--color-gray-800)] hover:bg-[var(--color-gray-200)] active:scale-[0.98]',
  ghost: 'bg-transparent text-[var(--color-gray-600)] hover:bg-[var(--color-gray-50)] hover:text-[var(--color-gray-900)]',
  danger: 'bg-[var(--color-error)] text-white hover:opacity-90 active:scale-[0.98]',
};

const sizes = {
  sm: 'px-3 py-1.5 text-sm rounded-[var(--radius-md)]',
  md: 'px-4 py-2 text-sm rounded-[var(--radius-lg)]',
  lg: 'px-6 py-3 text-base rounded-[var(--radius-lg)]',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  children,
  className,
  ...props
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-medium',
        'transition-all duration-150 ease-out',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary-500)] focus-visible:ring-offset-2',
        'disabled:opacity-50 disabled:pointer-events-none',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
```

### Input

```jsx
export default function Input({
  label,
  error,
  className,
  ...props
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-[var(--color-gray-700)]">
          {label}
        </label>
      )}
      <input
        className={cn(
          'w-full px-3.5 py-2.5 rounded-[var(--radius-lg)]',
          'bg-white border border-[var(--color-gray-200)]',
          'text-[var(--color-gray-900)] placeholder:text-[var(--color-gray-400)]',
          'transition-all duration-150',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)]/20 focus:border-[var(--color-primary-500)]',
          error && 'border-[var(--color-error)] focus:ring-[var(--color-error)]/20',
          className
        )}
        {...props}
      />
      {error && (
        <p className="text-sm text-[var(--color-error)]">{error}</p>
      )}
    </div>
  );
}
```

### Badge

```jsx
const variants = {
  default: 'bg-[var(--color-gray-100)] text-[var(--color-gray-700)]',
  primary: 'bg-[var(--color-primary-50)] text-[var(--color-primary-700)]',
  success: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-700',
  error: 'bg-red-50 text-red-700',
};

export default function Badge({ variant = 'default', children, className }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5',
        'text-xs font-medium rounded-[var(--radius-md)]',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
```

### 其他常见 Atoms

根据项目需要按需创建，常见的还包括：
- **Avatar** — 用户头像（支持图片 / 首字母 fallback / 尺寸 variants）
- **Icon** — 图标包装器（统一尺寸和颜色的管理）
- **Text** — 文本组件（统一 heading / body / caption 的样式）
- **Divider** — 分隔线
- **Skeleton** — 加载占位

---

## Molecules — 分子组合

Molecules 由 2-3 个 atoms 组合，形成一个小型完整功能。

### StatCard

```jsx
import Badge from '@/components/atoms/Badge';

export default function StatCard({
  label,
  value,
  change,
  trend = 'up',
  icon: Icon,
  className,
}) {
  return (
    <div
      className={cn(
        'p-6 rounded-[var(--radius-xl)] bg-[var(--surface-elevated)]',
        'border border-[var(--color-gray-100)]',
        'shadow-[var(--shadow-xs)]',
        'hover:shadow-[var(--shadow-sm)] transition-shadow duration-200',
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-[var(--color-gray-500)]">{label}</span>
        {Icon && (
          <div className="p-2 rounded-[var(--radius-lg)] bg-[var(--color-primary-50)]">
            <Icon className="w-4 h-4 text-[var(--color-primary-500)]" />
          </div>
        )}
      </div>
      <div className="flex items-end gap-3">
        <span
          className="text-3xl font-semibold text-[var(--color-gray-900)]"
          style={{ fontFamily: 'var(--font-display)', letterSpacing: 'var(--tracking-tight)' }}
        >
          {value}
        </span>
        {change && (
          <Badge variant={trend === 'up' ? 'success' : 'error'}>
            {trend === 'up' ? '↑' : '↓'} {change}
          </Badge>
        )}
      </div>
    </div>
  );
}
```

### SearchBar

```jsx
import Input from '@/components/atoms/Input';
import Button from '@/components/atoms/Button';

export default function SearchBar({ onSearch, placeholder = '搜索...', className }) {
  const [query, setQuery] = useState('');

  return (
    <div className={cn('flex gap-2', className)}>
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        onKeyDown={(e) => e.key === 'Enter' && onSearch?.(query)}
        className="flex-1"
      />
      <Button variant="secondary" onClick={() => onSearch?.(query)}>
        搜索
      </Button>
    </div>
  );
}
```

### 其他常见 Molecules

- **NavItem** — Icon + Label（+ 可选的 badge 计数）
- **FormField** — Label + Input + Help text + Error message
- **UserInfo** — Avatar + Name + Role
- **EmptyState** — Icon + Title + Description + Action button

---

## Organisms — 有机体

Organisms 是独立的功能区块，可以放在页面的任何位置。

### Header（示例结构）

```jsx
import Button from '@/components/atoms/Button';
import Avatar from '@/components/atoms/Avatar';
import NavItem from '@/components/molecules/NavItem';

export default function Header({ navigation = [], user, onAction }) {
  return (
    <header className={cn(
      'flex items-center justify-between',
      'px-8 h-16',
      'border-b border-[var(--color-gray-100)]',
      'bg-[var(--surface-elevated)]/80 backdrop-blur-md',
      'sticky top-0 z-[var(--z-sticky)]'
    )}>
      {/* Logo */}
      <div className="flex items-center gap-8">
        <span
          className="text-lg font-bold text-[var(--color-gray-900)]"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          ProductName
        </span>
        <nav className="flex items-center gap-1">
          {navigation.map(item => (
            <NavItem key={item.href} {...item} />
          ))}
        </nav>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        <Button variant="primary" size="sm" onClick={onAction}>
          New Project
        </Button>
        <Avatar src={user?.avatar} name={user?.name} size="sm" />
      </div>
    </header>
  );
}
```

### 设计 Organism 的原则

- 通过 props 接收数据，不在内部硬编码内容
- 保持合理的 props 数量（如果超过 8 个 props，考虑是否应拆分）
- 可以管理自己的局部状态（如展开/收起、当前选中项）
- 全局状态（如用户信息、路由）通过 props 或 context 注入

---

## Templates — 布局模板

Templates 只负责定义空间布局，不包含具体内容。

### DashboardLayout

```jsx
export default function DashboardLayout({
  sidebar,
  header,
  children,
  className,
}) {
  return (
    <div className="flex h-screen bg-[var(--surface-primary)]">
      {/* Sidebar */}
      {sidebar && (
        <aside className="w-64 flex-shrink-0 border-r border-[var(--color-gray-100)] bg-[var(--surface-elevated)]">
          {sidebar}
        </aside>
      )}

      {/* Main content area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {header}
        <main className={cn(
          'flex-1 overflow-auto',
          'p-8',
          className
        )}>
          {children}
        </main>
      </div>
    </div>
  );
}
```

### 常见布局模板

- **DashboardLayout** — 侧边栏 + 顶栏 + 内容区
- **MarketingLayout** — 全宽顶栏 + 全宽内容区 + 页脚
- **AuthLayout** — 居中卡片 + 背景装饰
- **SettingsLayout** — 左侧导航 + 右侧内容（嵌套在 DashboardLayout 中）

---

## Pages — 页面实例

Pages 把 Template + Organisms 组装在一起，注入具体数据。

```jsx
import DashboardLayout from '@/components/templates/DashboardLayout';
import Header from '@/components/organisms/Header';
import Sidebar from '@/components/organisms/Sidebar';
import StatCard from '@/components/molecules/StatCard';
import DataTable from '@/components/organisms/DataTable';
import { dashboardData } from '@/lib/constants';

export default function DashboardPage() {
  return (
    <DashboardLayout
      sidebar={<Sidebar items={dashboardData.navigation} />}
      header={<Header user={dashboardData.user} />}
    >
      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        {dashboardData.stats.map((stat, i) => (
          <StatCard
            key={stat.label}
            {...stat}
            className="animate-in"
            style={{ animationDelay: `${i * 80}ms` }}
          />
        ))}
      </div>

      {/* Data table */}
      <DataTable
        columns={dashboardData.columns}
        data={dashboardData.rows}
        className="animate-in"
        style={{ animationDelay: '320ms' }}
      />
    </DashboardLayout>
  );
}
```

---

## Variant 模式

所有支持多种视觉变体的组件，使用统一的 variants 对象模式：

```jsx
// 定义变体映射
const variants = {
  primary: '...',
  secondary: '...',
  ghost: '...',
};

// 定义尺寸映射
const sizes = {
  sm: '...',
  md: '...',
  lg: '...',
};

// 组件接收 variant 和 size props，有默认值
export default function Component({ variant = 'primary', size = 'md', ... }) {
  // 通过映射应用样式
  className={cn(baseStyles, variants[variant], sizes[size], className)}
}
```

**优势**：PM 要改某种按钮的样式，只需修改 variants 对象中对应的值。不需要搜索所有使用这个按钮的地方。

---

## 组件接口设计规范

### 必须遵循的规则

1. **每个组件都接受 `className` prop**，使用 `cn()` 合并，允许外部微调
2. **所有 props 都有合理的默认值**，组件在无 props 时也能渲染出有意义的内容
3. **事件处理用 `onXxx` 命名**：`onClick`, `onChange`, `onSearch`, `onSelect`
4. **数据 props 和 UI props 分离**：`data` / `items` 是数据，`variant` / `size` 是 UI 控制
5. **复合内容用 `children`**，不要用 `content` string prop

### cn() 工具函数

每个项目需要这个工具函数来合并 Tailwind classes：

```js
// src/lib/utils.js
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
```

如果项目不想引入 `clsx` 和 `tailwind-merge`，可用简化版：

```js
export function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}
```

---

## 常见陷阱

### ❌ 把所有东西写在一个文件里
即使是 demo，也不要把 Header、Table、Card 全写在一个 Page 文件中。每个组件单独一个文件，import 进来。这样 PM 说"把表头改一下"时你能精准定位。

### ❌ Atom 里面 import 其他自定义组件
Atom 是最底层的。如果一个"按钮"需要 import 一个"图标组件"，那这个按钮可能其实是个 molecule。

### ❌ 样式硬编码在页面里
```jsx
// ❌ Bad
<div className="bg-blue-500 text-white px-4 py-2 rounded-lg">按钮</div>

// ✅ Good — 使用 Button atom
<Button variant="primary">按钮</Button>
```

### ❌ 每个组件的圆角/间距/颜色值各不相同
所有值都应该来自 design tokens，而不是在每个组件里写死不同的魔法数字。

### ❌ Mock 数据散落在各个组件里
集中放在 `src/lib/constants.js` 中，页面 import 后注入。方便 PM 统一修改数据。
