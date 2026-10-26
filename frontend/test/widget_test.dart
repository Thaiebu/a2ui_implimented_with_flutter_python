import 'package:flutter_test/flutter_test.dart';
import 'package:a2ui_client/main.dart';

void main() {
  testWidgets('A2UI App Studio smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const A2UIApp(autoConnect: false));
    expect(find.text('A2UI'), findsOneWidget);
    expect(find.text('Saved Apps'), findsOneWidget);
  });
}
