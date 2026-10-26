# Flutter A2UI Integration & Architecture Guide

This guide details how to implement an **A2UI (Agent-to-User Interface)** client renderer using Flutter.

---

## 1. Core Mechanics

In A2UI, the Flutter client is responsible for:
1. **Listening to streaming protocol messages** (`createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`).
2. **Maintaining a reactive state model** (`DataModelStore`) indexed by JSON Pointer paths (RFC 6901).
3. **Translating flat component lists** into a nested Flutter widget tree using a Component Catalog.
4. **Dispatching user actions** back to the agent backend.

---

## 2. DataModelStore: RFC 6901 JSON Pointer Binding

Components in A2UI bind their properties (like labels, values, visibility) to JSON Pointer paths rather than static values. This allows the backend to update data models dynamically without re-sending the layout.

```dart
import 'package:flutter/foundation.dart';

/// Reactive state store that supports RFC 6901 JSON Pointer path evaluation.
class DataModelStore extends ChangeNotifier {
  final Map<String, dynamic> _data = {};

  Map<String, dynamic> get rawData => Map.unmodifiable(_data);

  /// Retrieve a value using a JSON pointer path, e.g. "/restaurant/name" or "/items/0/id"
  dynamic getValue(String pointer) {
    if (pointer.isEmpty || pointer == '/') return _data;
    
    // Normalize and split tokens
    final tokens = pointer.split('/').skip(1).map((t) => 
      t.replaceAll('~1', '/').replaceAll('~0', '~')
    );
    
    dynamic current = _data;
    for (final token in tokens) {
      if (current is Map) {
        current = current[token];
      } else if (current is List) {
        final index = int.tryParse(token);
        if (index != null && index >= 0 && index < current.length) {
          current = current[index];
        } else {
          return null;
        }
      } else {
        return null;
      }
    }
    return current;
  }

  /// Update data at a pointer path and notify listeners
  void updatePointer(String pointer, dynamic value) {
    if (pointer.isEmpty || pointer == '/') {
      if (value is Map<String, dynamic>) {
        _data.addAll(value);
      }
      notifyListeners();
      return;
    }

    final tokens = pointer.split('/').skip(1).toList();
    Map<String, dynamic> current = _data;
    
    for (int i = 0; i < tokens.length - 1; i++) {
      final token = tokens[i];
      if (!current.containsKey(token) || current[token] is! Map) {
        current[token] = <String, dynamic>{};
      }
      current = current[token] as Map<String, dynamic>;
    }
    
    current[tokens.last] = value;
    notifyListeners();
  }
}
```

---

## 3. Dynamic Value Resolver

A dynamic property in A2UI can either be a literal string or a JSON pointer path:

```dart
class DynamicString {
  final String? literal;
  final String? path;

  DynamicString({this.literal, this.path});

  factory DynamicString.fromJson(Map<String, dynamic> json) {
    return DynamicString(
      literal: json['literalString'] as String?,
      path: json['path'] as String?,
    );
  }

  String resolve(DataModelStore store, {String defaultValue = ''}) {
    if (literal != null) return literal!;
    if (path != null) {
      final val = store.getValue(path!);
      return val?.toString() ?? defaultValue;
    }
    return defaultValue;
  }
}
```

---

## 4. Component Catalog & Widget Factory

The Catalog defines what widgets the AI Agent is allowed to create:

```dart
import 'package:flutter/material.dart';

abstract class A2UIWidgetBuilder {
  Widget build({
    required BuildContext context,
    required Map<String, dynamic> componentData,
    required DataModelStore dataModel,
    required Widget Function(String childId) buildChild,
    required void Function(String action, Map<String, dynamic> payload) onAction,
  });
}

class ColumnWidgetBuilder extends A2UIWidgetBuilder {
  @override
  Widget build({
    required BuildContext context,
    required Map<String, dynamic> componentData,
    required DataModelStore dataModel,
    required Widget Function(String childId) buildChild,
    required void Function(String action, Map<String, dynamic> payload) onAction,
  }) {
    final childrenIds = (componentData['children']?['explicitList'] as List<dynamic>?)
            ?.cast<String>() ??
        [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: childrenIds.map((id) => buildChild(id)).toList(),
    );
  }
}

class TextWidgetBuilder extends A2UIWidgetBuilder {
  @override
  Widget build({
    required BuildContext context,
    required Map<String, dynamic> componentData,
    required DataModelStore dataModel,
    required Widget Function(String childId) buildChild,
    required void Function(String action, Map<String, dynamic> payload) onAction,
  }) {
    final textProp = DynamicString.fromJson(componentData['text'] as Map<String, dynamic>);
    final usageHint = componentData['usageHint'] as String? ?? 'body';
    
    TextStyle style;
    switch (usageHint) {
      case 'h1':
        style = Theme.of(context).textTheme.headlineMedium ?? const TextStyle(fontSize: 22, fontWeight: FontWeight.bold);
        break;
      case 'h2':
        style = Theme.of(context).textTheme.titleLarge ?? const TextStyle(fontSize: 18, fontWeight: FontWeight.w600);
        break;
      case 'caption':
        style = Theme.of(context).textTheme.bodySmall ?? const TextStyle(fontSize: 12, color: Colors.grey);
        break;
      default:
        style = Theme.of(context).textTheme.bodyMedium ?? const TextStyle(fontSize: 14);
    }

    return Text(textProp.resolve(dataModel), style: style);
  }
}

class ButtonWidgetBuilder extends A2UIWidgetBuilder {
  @override
  Widget build({
    required BuildContext context,
    required Map<String, dynamic> componentData,
    required DataModelStore dataModel,
    required Widget Function(String childId) buildChild,
    required void Function(String action, Map<String, dynamic> payload) onAction,
  }) {
    final textProp = DynamicString.fromJson(componentData['text'] as Map<String, dynamic>);
    final action = componentData['action'] as Map<String, dynamic>?;
    final actionName = action?['name'] as String? ?? 'click';
    final contextPath = action?['contextPath'] as String? ?? '/';

    return ElevatedButton(
      onPressed: () {
        final payload = dataModel.getValue(contextPath);
        onAction(
          actionName,
          payload is Map<String, dynamic> ? payload : {'value': payload},
        );
      },
      child: Text(textProp.resolve(dataModel)),
    );
  }
}
```

---

## 5. Official Flutter `genui` SDK Option

Google provides the official experimental `genui` package on pub.dev:

```yaml
dependencies:
  flutter:
    sdk: flutter
  genui: ^0.10.4
  genui_catalog: ^0.5.0
  genui_a2a: ^0.3.0
```

Using `genui` allows:
- Immediate drop-in compatibility with Google's reference A2A agents.
- Pre-built Material 3 catalog widgets.
- Built-in connection to agent streams over WebSockets.
