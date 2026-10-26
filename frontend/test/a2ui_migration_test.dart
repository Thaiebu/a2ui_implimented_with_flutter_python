import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:genui/genui.dart';
import 'package:a2ui_core/a2ui_core.dart' as core;
import 'package:a2ui_client/services/a2ui_normalizer.dart';

void main() {
  testWidgets('Normalizer enables legacy scenarios to run on official genui Surface', (tester) async {
    final catalog = BasicCatalogItems.asCatalog();
    final controller = SurfaceController(catalogs: [catalog]);

    final rawCreate = {
      'version': 'v0.9',
      'createSurface': {
        'surfaceId': 'intro_surface',
      },
    };
    controller.handleMessage(core.A2uiMessage.fromJson(normalizeA2uiMessage(rawCreate)));

    final rawUpdate = {
      'version': 'v0.9',
      'updateComponents': {
        'surfaceId': 'intro_surface',
        'components': [
          {
            'id': 'root_col',
            'component': 'Column',
            'children': {
              'explicitList': ['intro_title', 'profile_card', 'action_btn'],
            },
          },
          {
            'id': 'intro_title',
            'component': 'Text',
            'text': {'literalString': '🤖 Agent-to-UI Assistant'},
          },
          {
            'id': 'profile_card',
            'component': 'Card',
            'children': {
              'explicitList': ['profile_heading'],
            },
          },
          {
            'id': 'profile_heading',
            'component': 'Text',
            'text': {'literalString': 'Flight Reservation Assistant'},
          },
          {
            'id': 'action_btn',
            'component': 'Button',
            'text': {'literalString': '✈️ Launch Reservation'},
            'action': {
              'name': 'quick_launch_flight',
            },
          },
        ],
      },
    };

    final normalized = normalizeA2uiMessage(rawUpdate);
    controller.handleMessage(core.A2uiMessage.fromJson(normalized));

    final surfaceContext = controller.contextFor('intro_surface');
    expect(surfaceContext.definition.value, isNotNull);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Surface(surfaceContext: surfaceContext),
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('🤖 Agent-to-UI Assistant'), findsOneWidget);
    expect(find.text('Flight Reservation Assistant'), findsOneWidget);
    expect(find.text('✈️ Launch Reservation'), findsOneWidget);
  });

  testWidgets('ChoicePicker with {literalString: Select one} correctly renders plain text label', (tester) async {
    final catalog = BasicCatalogItems.asCatalog();
    final controller = SurfaceController(catalogs: [catalog]);

    final rawCreate = {
      'version': 'v0.9',
      'createSurface': {
        'surfaceId': 'picker_surface',
      },
    };
    controller.handleMessage(core.A2uiMessage.fromJson(normalizeA2uiMessage(rawCreate)));

    final rawUpdate = {
      'version': 'v0.9',
      'updateComponents': {
        'surfaceId': 'picker_surface',
        'components': [
          {
            'id': 'root',
            'component': 'Column',
            'children': ['my_picker'],
          },
          {
            'id': 'my_picker',
            'component': 'ChoicePicker',
            'label': {'literalString': 'Select one'},
            'options': [
              {'label': {'literalString': 'Red'}, 'value': 'red'},
              {'label': {'literalString': 'Blue'}, 'value': 'blue'},
            ],
            'value': 'red',
          },
        ],
      },
    };

    final normalized = normalizeA2uiMessage(rawUpdate);
    controller.handleMessage(core.A2uiMessage.fromJson(normalized));

    final surfaceContext = controller.contextFor('picker_surface');
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Surface(surfaceContext: surfaceContext),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify it renders "Select one", NOT "{literalString: Select one}"
    expect(find.text('Select one'), findsOneWidget);
    expect(find.textContaining('{literalString'), findsNothing);
    expect(find.text('Red'), findsOneWidget);
    expect(find.text('Blue'), findsOneWidget);
  });
}
