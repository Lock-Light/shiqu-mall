/** Run two JVMs concurrently: synchronized protects only this JVM's monitor. */
public class JvmLockProbe {
    public static void main(String[] args) throws Exception {
        synchronized(JvmLockProbe.class) {
            long begin=System.currentTimeMillis();Thread.sleep(2500);long end=System.currentTimeMillis();
            System.out.println("{\"begin\":"+begin+",\"end\":"+end+"}");
        }
    }
}
